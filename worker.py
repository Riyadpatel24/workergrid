import time

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.task import Task

from app.queue.redis_client import redis_client


def process_task(task_id: int):

    db: Session = SessionLocal()

    try:

        task = db.query(Task).filter(
            Task.id == task_id
        ).first()

        if not task:
            return

        task.status = "PROCESSING"

        db.commit()

        time.sleep(5)

        task.status = "SUCCESS"

        task.result = {
            "message": "processed successfully"
        }

        db.commit()

        print(f"Task {task_id} completed")

    finally:
        db.close()


while True:

    task = redis_client.lpop("task_queue")

    if task:

        process_task(int(task))

    time.sleep(1)