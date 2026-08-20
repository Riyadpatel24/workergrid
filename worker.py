import os
import socket
import time
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.core.time import utcnow_naive
from app.models.task import Task
from app.queue.queue_manager import enqueue_task
from app.queue.redis_client import redis_client
from app.services.workflow_manager import release_dependents

WORKER_ID = os.getpid()
HOSTNAME = socket.gethostname()
WORKER_VERSION = "3.0"
CAPABILITIES = [x.strip() for x in os.getenv("WORKER_CAPABILITIES", "general").split(",") if x.strip()]
MAX_RETRIES = 3
BASE_DELAY = 2


def worker_key():
    return f"worker:{WORKER_ID}"


def send_heartbeat():
    now = int(time.time())
    redis_client.hset("worker_heartbeats", WORKER_ID, now)
    redis_client.hset(worker_key(), "last_heartbeat", now)


def clear_current_task():
    redis_client.hset(worker_key(), mapping={"status": "ONLINE", "current_task": ""})


def process_task(task_id: int):
    db: Session = SessionLocal()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task or task.status in {"CANCELLED", "SUCCESS"}:
            return

        required = task.required_capability
        if required and required not in CAPABILITIES and "*" not in CAPABILITIES:
            # Return the task to its queue rather than claiming work this worker cannot execute.
            enqueue_task(task.id, task.priority)
            return

        task.status = "PROCESSING"
        task.started_at = utcnow_naive()
        task.worker_id = WORKER_ID
        db.commit()

        redis_client.hset(worker_key(), mapping={"status": "BUSY", "current_task": task.id})
        print(f"[Worker {WORKER_ID}] Task {task_id} started")

        if task.payload.get("crash"):
            print(f"[Worker {WORKER_ID}] Simulating crash...")
            os._exit(1)

        duration = max(0, min(int(task.payload.get("duration", 2)), 300))
        time.sleep(duration)

        if task.payload.get("fail"):
            raise Exception("Simulated failure")

        task.status = "SUCCESS"
        task.completed_at = utcnow_naive()
        task.result = {"message": "processed successfully"}
        task.retries = 0
        db.commit()
        release_dependents(db, task)

        redis_client.hset(worker_key(), mapping={"status": "ONLINE", "current_task": ""})
        redis_client.hincrby(worker_key(), "completed_tasks", 1)
        print(f"[Worker {WORKER_ID}] Task {task_id} completed")

    except Exception as exc:
        if task is None:
            return
        task.last_error = str(exc)
        task.retries = (task.retries or 0) + 1
        delay = BASE_DELAY ** task.retries

        if task.retries < task.max_retries:
            task.status = "PENDING"
            task.started_at = None
            task.completed_at = None
            db.commit()
            clear_current_task()
            print(f"[Worker {WORKER_ID}] Retry {task.retries} in {delay} seconds...")
            time.sleep(delay)
            enqueue_task(task.id, task.priority)
            print(f"[Worker {WORKER_ID}] Task {task_id} retry {task.retries}")
        else:
            task.status = "FAILED"
            task.completed_at = utcnow_naive()
            task.result = {"error": str(exc)}
            db.commit()
            redis_client.rpush("dead_letter_queue", task.id)
            clear_current_task()
            redis_client.hincrby(worker_key(), "failed_tasks", 1)
            release_dependents(db, task)
            print(f"[Worker {WORKER_ID}] Task {task_id} moved to DLQ")
    finally:
        db.close()


def register_worker():
    redis_client.hset(worker_key(), mapping={
        "worker_id": WORKER_ID,
        "hostname": HOSTNAME,
        "status": "ONLINE",
        "started_at": int(time.time()),
        "last_heartbeat": int(time.time()),
        "current_task": "",
        "completed_tasks": 0,
        "failed_tasks": 0,
        "version": WORKER_VERSION,
        "capabilities": ",".join(CAPABILITIES),
    })
    print(f"[Worker {WORKER_ID}] Registered capabilities={CAPABILITIES}")


register_worker()

while True:
    send_heartbeat()
    task = redis_client.lpop("high_priority_queue")
    if not task:
        task = redis_client.lpop("medium_priority_queue")
    if not task:
        task = redis_client.lpop("low_priority_queue")
    if task:
        process_task(int(task))
    time.sleep(1)
