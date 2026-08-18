from datetime import datetime, UTC
import time

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.task import Task
from app.queue.redis_client import redis_client


CHECK_INTERVAL = 5


def schedule_tasks():

    db: Session = SessionLocal()

    try:

        ready_tasks = db.query(Task).filter(
            Task.status == "SCHEDULED",
            Task.scheduled_at <= datetime.now(UTC).replace(tzinfo=None)
        ).all()

        for task in ready_tasks:

            print(
                f"[Scheduler] Activating Task {task.id}"
            )

            task.status = "PENDING"

            redis_client.rpush(
                "task_queue",
                task.id
            )

        db.commit()

    finally:

        db.close()


print("Scheduler Service Started...")

while True:

    schedule_tasks()

    time.sleep(CHECK_INTERVAL)