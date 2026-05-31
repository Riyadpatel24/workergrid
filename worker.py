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

        print(f"Task {task_id} started")

        time.sleep(5)

        if task.payload.get("fail"):

            raise Exception("Simulated failure")

        task.status = "SUCCESS"

        task.result = {
            "message": "processed successfully"
        }

        db.commit()

        print(f"Task {task_id} completed")

    except Exception as e:

        task.retries = (task.retries or 0) + 1

        if task.retries < 3:

            task.status = "PENDING"

            db.commit()

            redis_client.rpush(
                "task_queue",
                task.id
            )

            print(
                f"Task {task_id} retry {task.retries}"
            )

        else:

            task.status = "FAILED"

            task.result = {
                "error": str(e)
            }

            db.commit()

            redis_client.rpush(
                "dead_letter_queue",
                task.id
            )

            print(
                f"Task {task_id} moved to DLQ"
            )

    finally:

        db.close()

while True:

    task = redis_client.lpop("task_queue")

    if task:

        process_task(int(task))

    time.sleep(1)