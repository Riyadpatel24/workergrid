from datetime import datetime, timedelta
import time

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.task import Task
from app.queue.redis_client import redis_client

TIMEOUT_SECONDS = 30
CHECK_INTERVAL = 10


def recover_tasks():

    db: Session = SessionLocal()

    try:

        timeout_time = datetime.utcnow() - timedelta(
            seconds=TIMEOUT_SECONDS
        )

        stuck_tasks = db.query(Task).filter(
            Task.status == "PROCESSING",
            Task.started_at.isnot(None),
            Task.started_at < timeout_time
        ).all()

        for task in stuck_tasks:

            print(
                f"[Recovery] Task {task.id} timed out. "
                f"Requeuing (Retry {task.retries + 1}/{task.max_retries})"
            )

            if task.retries < task.max_retries:

                task.status = "PENDING"
                
                task.started_at = None
                task.completed_at = None

                task.retries += 1

                task.last_error = "Worker timeout"

                db.commit()

                redis_client.rpush(
                    "task_queue",
                    task.id
                )

            else:

                task.status = "FAILED"

                task.last_error = "Worker timeout"

                db.commit()

                redis_client.rpush(
                    "dead_letter_queue",
                    task.id
                )

                print(
                    f"[Recovery] Task {task.id} exceeded timeout retries. "
                    f"Moved to DLQ."
                )

    finally:

        db.close()


print("Recovery Monitor Started...")

while True:

    recover_tasks()

    time.sleep(CHECK_INTERVAL)