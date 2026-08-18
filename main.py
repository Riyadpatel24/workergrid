from app.queue.queue_manager import enqueue_task
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI
from fastapi import Depends

from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.database import engine

from app.db.dependencies import get_db

from app.queue.redis_client import redis_client

from app.models.task import Task

from app.api.schemas import TaskCreate

from datetime import datetime, timedelta

import time


Base.metadata.create_all(bind=engine)

app = FastAPI()

templates = Jinja2Templates(
    directory="app/templates"
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


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
        status=(
            "SCHEDULED"
            if task.delay > 0
            else "PENDING"
        ),
        
        priority=task.priority,
        
        scheduled_at=(
            datetime.utcnow()
            + timedelta(seconds=task.delay)
        )
    )

    db.add(new_task)

    db.commit()

    db.refresh(new_task)
    
    if task.delay == 0:
        enqueue_task(
            new_task.id,
            new_task.priority
        )

    return {
        "task_id": new_task.id,
        "status": new_task.status,
        "priority": new_task.priority,
        "scheduled_at": new_task.scheduled_at,
        "queued": task.delay == 0
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

    worker_keys = redis_client.keys("worker:*")

    workers = []

    for key in worker_keys:

        worker = redis_client.hgetall(key)

        workers.append({

            "worker_id": int(worker["worker_id"]),

            "hostname": worker["hostname"],

            "status": worker["status"],

            "started_at": int(worker["started_at"]),

            "last_heartbeat": int(worker["last_heartbeat"]),

            "current_task": (
                int(worker["current_task"])
                if worker["current_task"]
                else None
            ),

            "completed_tasks": int(worker["completed_tasks"]),

            "failed_tasks": int(worker["failed_tasks"]),

            "version": worker["version"]

        })

    return workers

@app.get("/stats")
def get_stats(
    db: Session = Depends(get_db)
):

    # Queue Metrics
    queued_tasks = redis_client.llen("task_queue")
    dead_letter_tasks = redis_client.llen("dead_letter_queue")
    
    high_priority_tasks = redis_client.llen(
        "high_priority_queue"
    )

    medium_priority_tasks = redis_client.llen(
        "medium_priority_queue"
    )

    low_priority_tasks = redis_client.llen(
        "low_priority_queue"
    )

    # Worker Metrics
    worker_keys = redis_client.keys("worker:*")

    online_workers = 0
    busy_workers = 0

    for key in worker_keys:

        status = redis_client.hget(key, "status")

        if status == "ONLINE":
            online_workers += 1

        elif status == "BUSY":
            busy_workers += 1

    # Task Metrics
    pending_tasks = db.query(Task).filter(
        Task.status == "PENDING"
    ).count()

    processing_tasks = db.query(Task).filter(
        Task.status == "PROCESSING"
    ).count()

    scheduled_tasks = db.query(Task).filter(
        Task.status == "SCHEDULED"
    ).count()

    successful_tasks = db.query(Task).filter(
        Task.status == "SUCCESS"
    ).count()

    failed_tasks = db.query(Task).filter(
        Task.status == "FAILED"
    ).count()

    # Performance Metrics
    completed_tasks = db.query(Task).filter(
        Task.started_at.isnot(None),
        Task.completed_at.isnot(None)
    ).all()

    total_time = 0

    for task in completed_tasks:
        total_time += (
            task.completed_at -
            task.started_at
        ).total_seconds()

    average_processing_time = (
        total_time / len(completed_tasks)
        if completed_tasks else 0
    )

    return {

        "workers": {
            "online": online_workers,
            "busy": busy_workers
        },

        "tasks": {
            "queued": queued_tasks,
            "pending": pending_tasks,
            "processing": processing_tasks,
            "scheduled": scheduled_tasks,
            "dead_letter": dead_letter_tasks,
            "priority_queues": {
                "high": high_priority_tasks,
                "medium": medium_priority_tasks,
                "low": low_priority_tasks
            }
        },

        "performance": {
            "successful": successful_tasks,
            "failed": failed_tasks,
            "average_processing_time": round(
                average_processing_time,
                2
            )
        }
    }
    
@app.get("/queues/priority")
def get_priority_queues():

    high_tasks = redis_client.llen(
        "high_priority_queue"
    )

    medium_tasks = redis_client.llen(
        "medium_priority_queue"
    )

    low_tasks = redis_client.llen(
        "low_priority_queue"
    )

    dead_letter_tasks = redis_client.llen(
        "dead_letter_queue"
    )

    return {
        "high": high_tasks,
        "medium": medium_tasks,
        "low": low_tasks,
        "dead_letter": dead_letter_tasks
    }

@app.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db)
):

    # ------------------------
    # Queue Metrics
    # ------------------------

    queued_tasks = redis_client.llen("task_queue")

    dead_letter_tasks = redis_client.llen(
        "dead_letter_queue"
    )
    
    high_priority_tasks = redis_client.llen(
        "high_priority_queue"
    )

    medium_priority_tasks = redis_client.llen(
        "medium_priority_queue"
    )

    low_priority_tasks = redis_client.llen(
        "low_priority_queue"
    )

    # ------------------------
    # Worker Metrics
    # ------------------------

    worker_keys = redis_client.keys("worker:*")

    online_workers = 0
    busy_workers = 0

    for key in worker_keys:

        status = redis_client.hget(
            key,
            "status"
        )

        if status == "ONLINE":
            online_workers += 1

        elif status == "BUSY":
            busy_workers += 1

    # ------------------------
    # Task Metrics
    # ------------------------

    pending_tasks = db.query(Task).filter(
        Task.status == "PENDING"
    ).count()

    processing_tasks = db.query(Task).filter(
        Task.status == "PROCESSING"
    ).count()

    scheduled_tasks = db.query(Task).filter(
        Task.status == "SCHEDULED"
    ).count()

    successful_tasks = db.query(Task).filter(
        Task.status == "SUCCESS"
    ).count()

    failed_tasks = db.query(Task).filter(
        Task.status == "FAILED"
    ).count()

    # ------------------------
    # Performance Metrics
    # ------------------------

    completed_tasks = db.query(Task).filter(
        Task.started_at.isnot(None),
        Task.completed_at.isnot(None)
    ).all()

    total_processing_time = 0

    for task in completed_tasks:

        total_processing_time += (
            task.completed_at -
            task.started_at
        ).total_seconds()

    average_processing_time = (
        total_processing_time /
        len(completed_tasks)
        if completed_tasks
        else 0
    )

    # ------------------------
    # Health Check
    # ------------------------

    alerts = []

    system_status = "HEALTHY"

    if queued_tasks > 10:

        alerts.append(
            "High Task Queue Size"
        )

    if dead_letter_tasks > 0:

        alerts.append(
            f"{dead_letter_tasks} task(s) in Dead Letter Queue"
        )

    if (
        online_workers > 0 and
        busy_workers == online_workers
    ):

        alerts.append(
            "All Workers Are Busy"
        )

    if len(alerts) > 0:

        system_status = "WARNING"

    # ------------------------
    # Dashboard Response
    # ------------------------

    return {

        "timestamp": datetime.utcnow(),

        "system_status": system_status,

        "workers": {

            "online": online_workers,

            "busy": busy_workers

        },

        "tasks": {

            "queued": queued_tasks,

            "pending": pending_tasks,

            "processing": processing_tasks,

            "scheduled": scheduled_tasks,

            "dead_letter": dead_letter_tasks,
            
            "priority_queues": {
                "high": high_priority_tasks,
                "medium": medium_priority_tasks,
                "low": low_priority_tasks
            }

        },

        "performance": {

            "successful": successful_tasks,

            "failed": failed_tasks,

            "average_processing_time": round(
                average_processing_time,
                2
            )

        },

        "alerts": alerts

    }
    
@app.get(
    "/console",
    response_class=HTMLResponse
)
def console(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="console.html"
    )