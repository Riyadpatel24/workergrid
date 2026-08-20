from datetime import datetime, timedelta
import time
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.core.time import utcnow_naive
from app.models.task import Task
from app.queue.queue_manager import enqueue_task
from app.queue.redis_client import redis_client
from app.services.workflow_manager import release_dependents

TIMEOUT_SECONDS = 30
CHECK_INTERVAL = 5


def recover_tasks():
    db: Session = SessionLocal()
    try:
        cutoff = utcnow_naive() - timedelta(seconds=TIMEOUT_SECONDS)
        stuck = db.query(Task).filter(
            Task.status == "PROCESSING",
            Task.started_at.isnot(None),
            Task.started_at < cutoff,
        ).all()
        for task in stuck:
            task.retries = (task.retries or 0) + 1
            task.last_error = "Worker timeout"
            if task.retries < task.max_retries:
                task.status = "PENDING"
                task.started_at = None
                task.completed_at = None
                db.commit()
                enqueue_task(task.id, task.priority)
                print(f"[Recovery] Requeued Task {task.id} after worker timeout")
            else:
                task.status = "FAILED"
                task.completed_at = utcnow_naive()
                db.commit()
                redis_client.rpush("dead_letter_queue", task.id)
                release_dependents(db, task)
                print(f"[Recovery] Task {task.id} moved to DLQ")
    finally:
        db.close()


print("Recovery Monitor Started...")
while True:
    recover_tasks()
    time.sleep(CHECK_INTERVAL)
