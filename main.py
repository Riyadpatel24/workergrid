import os
from datetime import datetime, timedelta
from uuid import uuid4


from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import TaskCreate, WorkflowCreate
from app.db.database import Base, engine
from app.db.dependencies import get_db
from app.models.task import Task
import app.models.friction  # noqa: F401 - Register Project Friction models with Base metadata
import app.models.user  # noqa: F401 - Register User models with Base metadata
from app.queue.queue_manager import enqueue_task, normalize_priority, queue_depths

from app.queue.redis_client import redis_client
from app.services.resource_manager import resource_snapshot
from app.core.time import utcnow_naive
from app.services.workflow_manager import release_dependents
from app.api.friction_router import router as friction_router
from app.api.auth_router import router as auth_router

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[Main] Warning: Could not run Base.metadata.create_all on startup: {e}")


app = FastAPI(title="WorkerGrid API", version="3.0.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(friction_router)


templates = Jinja2Templates(directory="app/templates")
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except RuntimeError:
    pass


def serialize_task(task: Task):
    processing_time = None
    if task.started_at and task.completed_at:
        processing_time = round((task.completed_at - task.started_at).total_seconds(), 2)

    return {
        "id": task.id,
        "type": task.type,
        "status": task.status,
        "priority": task.priority,
        "worker_id": task.worker_id,
        "required_capability": task.required_capability,
        "workflow_id": task.workflow_id,
        "workflow_key": task.workflow_key,
        "depends_on": task.depends_on or [],
        "retries": task.retries,
        "max_retries": task.max_retries,
        "scheduled_at": task.scheduled_at,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "processing_time": processing_time,
        "payload": task.payload,
        "result": task.result,
        "last_error": task.last_error,
    }


from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User


@app.get("/")
def root():
    return {"message": "WorkerGrid Running", "version": "3.0.0", "status": "healthy"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    checks = {"database": "ok", "redis": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"
    try:
        redis_client.ping()
    except Exception:
        checks["redis"] = "error"
    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks, "timestamp": utcnow_naive()}


@app.post("/tasks")
def create_task(
    task: TaskCreate,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    priority = normalize_priority(task.priority)
    now = utcnow_naive()
    user_id = current_user.id if current_user else None
    new_task = Task(
        user_id=user_id,
        type=task.type,
        payload=task.payload,
        status="SCHEDULED" if task.delay > 0 else "PENDING",
        priority=priority,
        max_retries=task.max_retries,
        required_capability=task.required_capability,
        scheduled_at=now + timedelta(seconds=task.delay),
        created_at=now,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    if task.delay == 0:
        enqueue_task(new_task.id, priority)
    return {
        "task_id": new_task.id,
        "status": new_task.status,
        "priority": new_task.priority,
        "scheduled_at": new_task.scheduled_at,
        "queued": task.delay == 0,
    }


@app.get("/tasks")
def list_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Task)
    if current_user:
        query = query.filter(Task.user_id == current_user.id)
    else:
        query = query.filter(Task.user_id.is_(None))

    if status:
        query = query.filter(Task.status == status.upper())
    tasks = query.order_by(Task.created_at.desc()).limit(limit).all()
    return {"items": [serialize_task(task) for task in tasks], "count": len(tasks), "limit": limit}


@app.get("/tasks/{task_id}")
def get_task(
    task_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Task).filter(Task.id == task_id)
    if current_user:
        query = query.filter(Task.user_id == current_user.id)
    else:
        query = query.filter(Task.user_id.is_(None))

    task = query.first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return serialize_task(task)


@app.post("/tasks/{task_id}/retry")
def retry_task(
    task_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Task).filter(Task.id == task_id)
    if current_user:
        query = query.filter(Task.user_id == current_user.id)
    else:
        query = query.filter(Task.user_id.is_(None))

    task = query.first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in {"FAILED", "SUCCESS"}:
        raise HTTPException(status_code=409, detail="Only completed tasks can be manually retried")
    task.status = "PENDING"
    task.started_at = None
    task.completed_at = None
    task.result = None
    task.last_error = None
    task.retries = 0
    db.commit()
    enqueue_task(task.id, task.priority)
    return serialize_task(task)


@app.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Task).filter(Task.id == task_id)
    if current_user:
        query = query.filter(Task.user_id == current_user.id)
    else:
        query = query.filter(Task.user_id.is_(None))

    task = query.first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in {"SUCCESS", "FAILED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail="Task is already terminal")
    task.status = "CANCELLED"
    task.completed_at = utcnow_naive()
    task.last_error = "Cancelled by operator."
    db.commit()
    return serialize_task(task)


@app.get("/workers")
def get_workers():
    workers = []
    now = int(utcnow_naive().timestamp())
    for key in redis_client.keys("worker:*"):
        worker = redis_client.hgetall(key)
        if not worker:
            continue
        last_heartbeat = int(worker.get("last_heartbeat", 0))
        status = worker.get("status", "UNKNOWN")
        if last_heartbeat and now - last_heartbeat > 60 and status != "BUSY":
            status = "OFFLINE"
        workers.append({
            "worker_id": int(worker["worker_id"]),
            "hostname": worker.get("hostname"),
            "status": status,
            "started_at": int(worker.get("started_at", 0)),
            "last_heartbeat": last_heartbeat,
            "current_task": int(worker["current_task"]) if worker.get("current_task") else None,
            "completed_tasks": int(worker.get("completed_tasks", 0)),
            "failed_tasks": int(worker.get("failed_tasks", 0)),
            "version": worker.get("version"),
            "capabilities": [x for x in worker.get("capabilities", "general").split(",") if x],
        })
    return workers


def task_metrics(db: Session):
    return {
        "pending": db.query(Task).filter(Task.status == "PENDING").count(),
        "processing": db.query(Task).filter(Task.status == "PROCESSING").count(),
        "scheduled": db.query(Task).filter(Task.status == "SCHEDULED").count(),
        "waiting": db.query(Task).filter(Task.status == "WAITING").count(),
        "successful": db.query(Task).filter(Task.status == "SUCCESS").count(),
        "failed": db.query(Task).filter(Task.status == "FAILED").count(),
        "cancelled": db.query(Task).filter(Task.status == "CANCELLED").count(),
    }


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    queues = queue_depths()
    workers = get_workers()
    metrics = task_metrics(db)
    completed = db.query(Task).filter(Task.started_at.isnot(None), Task.completed_at.isnot(None)).all()
    total_time = sum((t.completed_at - t.started_at).total_seconds() for t in completed)
    average = total_time / len(completed) if completed else 0
    return {
        "workers": {
            "registered": len(workers),
            "online": sum(1 for w in workers if w["status"] == "ONLINE"),
            "busy": sum(1 for w in workers if w["status"] == "BUSY"),
            "offline": sum(1 for w in workers if w["status"] == "OFFLINE"),
        },
        "tasks": {**metrics, "queued": queues["high"] + queues["medium"] + queues["low"], "dead_letter": queues["dead_letter"]},
        "priority_queues": {k: queues[k] for k in ("high", "medium", "low")},
        "performance": {"successful": metrics["successful"], "failed": metrics["failed"], "average_processing_time": round(average, 2)},
    }


@app.get("/queues/priority")
def get_priority_queues():
    return queue_depths()


@app.post("/workflows")
def create_workflow(
    workflow: WorkflowCreate,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    keys = {item.key for item in workflow.tasks}
    if len(keys) != len(workflow.tasks):
        raise HTTPException(status_code=422, detail="Workflow task keys must be unique")
    for item in workflow.tasks:
        missing = [dep for dep in item.depends_on if dep not in keys]
        if missing:
            raise HTTPException(status_code=422, detail=f"Unknown dependencies for {item.key}: {missing}")

    # Kahn-style cycle detection on the submitted DAG.
    remaining = {item.key: set(item.depends_on) for item in workflow.tasks}
    resolved = set()
    while remaining:
        ready = [key for key, deps in remaining.items() if deps <= resolved]
        if not ready:
            raise HTTPException(status_code=422, detail="Workflow contains a dependency cycle")
        for key in ready:
            resolved.add(key)
            remaining.pop(key)

    workflow_id = str(uuid4())
    key_to_id = {}
    now = utcnow_naive()
    user_id = current_user.id if current_user else None
    for item in workflow.tasks:
        task = Task(
            user_id=user_id,
            type=item.type,
            payload=item.payload,
            status="WAITING" if item.depends_on else ("SCHEDULED" if item.delay else "PENDING"),
            priority=normalize_priority(item.priority),
            max_retries=item.max_retries,
            required_capability=item.required_capability,
            workflow_id=workflow_id,
            workflow_key=item.key,
            scheduled_at=now + timedelta(seconds=item.delay),
            created_at=now,
            depends_on=[],
        )
        db.add(task)
        db.flush()
        key_to_id[item.key] = task.id

    for item in workflow.tasks:
        task = db.query(Task).filter(Task.workflow_id == workflow_id, Task.workflow_key == item.key).first()
        task.depends_on = [key_to_id[dep] for dep in item.depends_on]

    db.commit()
    tasks = db.query(Task).filter(Task.workflow_id == workflow_id).all()
    for task in tasks:
        if task.status == "PENDING":
            enqueue_task(task.id, task.priority)
    return {"workflow_id": workflow_id, "name": workflow.name, "tasks": [serialize_task(t) for t in tasks]}


@app.get("/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Task).filter(Task.workflow_id == workflow_id)
    if current_user:
        query = query.filter(Task.user_id == current_user.id)
    else:
        query = query.filter(Task.user_id.is_(None))

    tasks = query.order_by(Task.id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="Workflow not found")
    statuses = [task.status for task in tasks]
    if any(s == "FAILED" for s in statuses):
        status = "FAILED"
    elif all(s == "SUCCESS" for s in statuses):
        status = "SUCCESS"
    elif any(s == "PROCESSING" for s in statuses):
        status = "PROCESSING"
    else:
        status = "WAITING"
    return {"workflow_id": workflow_id, "status": status, "tasks": [serialize_task(t) for t in tasks]}



@app.get("/control-plane")
def control_plane(db: Session = Depends(get_db)):
    stats = get_stats(db)
    resources = resource_snapshot()
    return {
        "status": "healthy" if stats["workers"]["offline"] == 0 else "degraded",
        "resources": resources,
        "workers": stats["workers"],
        "queues": stats["priority_queues"],
        "tasks": stats["tasks"],
        "scaling": {
            "mode": "advisory",
            "recommended_workers": resources["recommended_workers"],
            "reason": "Based on current queue depth and busy workers.",
        },
    }


@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    stats = get_stats(db)
    workers = get_workers()
    alerts = []
    if stats["tasks"]["dead_letter"] > 0:
        alerts.append({"level": "warning", "message": f"{stats['tasks']['dead_letter']} task(s) need attention in the Dead Letter Queue."})
    if stats["workers"]["offline"] > 0:
        alerts.append({"level": "critical", "message": f"{stats['workers']['offline']} worker(s) have missed their heartbeat."})
    if stats["priority_queues"]["high"] > 10:
        alerts.append({"level": "warning", "message": "High-priority work is building up."})
    return {
        "timestamp": utcnow_naive(),
        "system_status": "CRITICAL" if any(a["level"] == "critical" for a in alerts) else "WARNING" if alerts else "HEALTHY",
        "workers": stats["workers"],
        "tasks": stats["tasks"],
        "priority_queues": stats["priority_queues"],
        "performance": stats["performance"],
        "active_tasks": [serialize_task(t) for t in db.query(Task).filter(Task.status == "PROCESSING").order_by(Task.started_at.desc()).limit(20).all()],
        "recent_tasks": [serialize_task(t) for t in db.query(Task).order_by(Task.created_at.desc()).limit(20).all()],
        "alerts": alerts,
        "worker_list": workers,
    }


@app.get("/console", response_class=HTMLResponse)
def console(request: Request):
    return templates.TemplateResponse(request=request, name="console.html")
