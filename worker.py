import os
import time
import socket
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.task import Task

from app.queue.redis_client import redis_client


WORKER_ID = os.getpid()

HOSTNAME = socket.gethostname()

WORKER_VERSION = "1.1"

MAX_RETRIES = 3
BASE_DELAY = 2      # seconds

def send_heartbeat():

    redis_client.hset(
        "worker_heartbeats",
        WORKER_ID,
        int(time.time())
    )

    redis_client.hset(
        f"worker:{WORKER_ID}",
        "last_heartbeat",
        int(time.time())
    )

def process_task(task_id: int):

    db: Session = SessionLocal()

    try:

        task = db.query(Task).filter(
            Task.id == task_id
        ).first()

        if not task:
            return

        task.status = "PROCESSING"
        task.started_at = datetime.utcnow()

        db.commit()

        redis_client.hset(
            f"worker:{WORKER_ID}",
            mapping={
                "status": "BUSY",
                "current_task": task.id
            }
        )

        print(
            f"[Worker {WORKER_ID}] Task {task_id} started"
        )
        if task.payload.get("crash"):
            print(f"[Worker {WORKER_ID}] Simulating Crash...")
            os._exit(1)

        time.sleep(20)

        if task.payload.get("fail"):

            raise Exception("Simulated failure")

        task.status = "SUCCESS"

        task.completed_at = datetime.utcnow()

        task.retries = 0

        task.result = {
            "message": "processed successfully"
        }

        db.commit()
        
        redis_client.hset(
            f"worker:{WORKER_ID}",
            mapping={
                "status": "ONLINE",
                "current_task": ""
            }
        )

        redis_client.hincrby(
            f"worker:{WORKER_ID}",
            "completed_tasks",
            1
        )

        print(
            f"[Worker {WORKER_ID}] Task {task_id} completed"
        )

    except Exception as e:
        
        task.last_error = str(e)

        task.retries = (task.retries or 0) + 1
        delay = BASE_DELAY ** task.retries

        if task.retries < MAX_RETRIES:

            task.status = "PENDING"

            db.commit()
            
            print(
                f"[Worker {WORKER_ID}] "
                f"Retry {task.retries} "
                f"in {delay} seconds..."
            )

            time.sleep(delay)

            redis_client.rpush(
                "task_queue",
                task.id
            )
            
            redis_client.hset(
                f"worker:{WORKER_ID}",
                mapping={
                    "status": "ONLINE",
                    "current_task": ""
                }
            )

            print(
                f"[Worker {WORKER_ID}] Task {task_id} retry {task.retries}"
            )

        else:

            task.status = "FAILED"

            task.completed_at = datetime.utcnow()

            task.result = {
                "error": str(e)
            }

            db.commit()

            redis_client.rpush(
                "dead_letter_queue",
                task.id
            )
            
            redis_client.hset(
                f"worker:{WORKER_ID}",
                mapping={
                    "status": "ONLINE",
                    "current_task": ""
                }
            )

            redis_client.hincrby(
                f"worker:{WORKER_ID}",
                "failed_tasks",
                1
            )

            print(
                f"[Worker {WORKER_ID}] Task {task_id} moved to DLQ"
            )

    finally:

        db.close()

def register_worker():

    redis_client.hset(
        f"worker:{WORKER_ID}",
        mapping={
            "worker_id": WORKER_ID,
            "hostname": HOSTNAME,
            "status": "ONLINE",
            "started_at": int(time.time()),
            "last_heartbeat": int(time.time()),
            "current_task": "",
            "completed_tasks": 0,
            "failed_tasks": 0,
            "version": WORKER_VERSION
        }
    )

    print(
        f"[Worker {WORKER_ID}] Registered"
    )

register_worker()

while True:

    send_heartbeat()

    task = redis_client.lpop("high_priority_queue")

    if not task:

        task = redis_client.lpop(
            "medium_priority_queue"
        )

    if not task:

        task = redis_client.lpop(
            "low_priority_queue"
        )

    if task:

        process_task(int(task))

    time.sleep(1)