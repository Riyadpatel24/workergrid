from fastapi import FastAPI
from fastapi import Depends

from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.database import engine

from app.db.dependencies import get_db

from app.queue.redis_client import redis_client

from app.models.task import Task

from app.api.schemas import TaskCreate

import time

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def root():
    return {
        "message": "WorkerGrid Running"
    }


@app.post("/tasks")
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    new_task = Task(
        type=task.type,
        payload=task.payload,
        status="PENDING"
    )

    db.add(new_task)

    db.commit()

    db.refresh(new_task)
    
    redis_client.rpush("task_queue", new_task.id)

    return {
        "task_id": new_task.id,
        "status": new_task.status,
        "queued": True
    }
    
@app.get("/tasks/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(
        Task.id == task_id
    ).first()

    if not task:
        return {
            "error": "Task not found"
        }

    return {
        "id": task.id,
        "type": task.type,
        "status": task.status,
        "payload": task.payload,
        "result": task.result
    }
    
@app.get("/workers")
def get_workers():

    workers = redis_client.hgetall(
        "worker_heartbeats"
    )

    result = []

    for worker_id, last_seen in workers.items():

        result.append({
            "worker_id": int(worker_id),
            "last_seen": int(last_seen)
        })

    return result

@app.get("/stats")
def get_stats(
    db: Session = Depends(get_db)
):

    queued_tasks = redis_client.llen(
        "task_queue"
    )

    dead_letter_tasks = redis_client.llen(
        "dead_letter_queue"
    )

    active_workers = len(
        redis_client.hgetall(
            "worker_heartbeats"
        )
    )

    successful_tasks = db.query(
        Task
    ).filter(
        Task.status == "SUCCESS"
    ).count()

    failed_tasks = db.query(
        Task
    ).filter(
        Task.status == "FAILED"
    ).count()

    return {

        "queued_tasks": queued_tasks,

        "dead_letter_tasks": dead_letter_tasks,

        "active_workers": active_workers,

        "successful_tasks": successful_tasks,

        "failed_tasks": failed_tasks
    }