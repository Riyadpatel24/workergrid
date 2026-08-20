from datetime import datetime
import time
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.core.time import utcnow_naive
from app.models.task import Task
from app.queue.queue_manager import enqueue_task

CHECK_INTERVAL = 2


def schedule_tasks():
    db: Session = SessionLocal()
    try:
        ready = db.query(Task).filter(
            Task.status == "SCHEDULED",
            Task.scheduled_at <= utcnow_naive(),
        ).all()
        for task in ready:
            task.status = "PENDING"
            enqueue_task(task.id, task.priority)
            print(f"[Scheduler] Activating Task {task.id}")
        db.commit()
    finally:
        db.close()


print("Scheduler Service Started...")
while True:
    schedule_tasks()
    time.sleep(CHECK_INTERVAL)
