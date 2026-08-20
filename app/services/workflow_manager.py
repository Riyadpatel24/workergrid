from datetime import datetime
from app.core.time import utcnow_naive
from app.models.task import Task
from app.queue.queue_manager import enqueue_task


def release_dependents(db, completed_task: Task):
    """Release tasks whose dependencies are now satisfied.

    Dependency state is durable in PostgreSQL. Redis is used only for ready work.
    """
    if not completed_task.workflow_id:
        return

    changed = True
    while changed:
        changed = False
        candidates = db.query(Task).filter(
            Task.workflow_id == completed_task.workflow_id,
            Task.status.in_(["WAITING", "SCHEDULED"]),
        ).all()

        status_by_id = {
            task.id: task.status
            for task in db.query(Task).filter(
                Task.workflow_id == completed_task.workflow_id
            ).all()
        }

        for task in candidates:
            dependency_ids = task.depends_on or []
            if not dependency_ids:
                continue

            dependency_statuses = [status_by_id.get(dep_id) for dep_id in dependency_ids]

            if any(status == "FAILED" for status in dependency_statuses):
                task.status = "FAILED"
                task.completed_at = utcnow_naive()
                task.last_error = "A workflow dependency failed."
                changed = True
                continue

            if all(status == "SUCCESS" for status in dependency_statuses):
                if task.scheduled_at and task.scheduled_at > utcnow_naive():
                    task.status = "SCHEDULED"
                else:
                    task.status = "PENDING"
                    enqueue_task(task.id, task.priority)
                changed = True

        if changed:
            db.commit()
