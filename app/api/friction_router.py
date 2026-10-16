import json
import urllib.request
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.api.schemas import WorkflowCreate, WorkflowTaskCreate
from app.core.security import decrypt_token
from app.core.time import utcnow_naive
from app.db.dependencies import get_db
from app.models.friction import (
    FrictionAnalysisRun,
    FrictionEvidence,
    FrictionIndicator,
    FrictionMetric,
    Repository,
)
from app.models.task import Task
from app.models.user import User, UserGitHubAccount
from app.queue.queue_manager import enqueue_task, normalize_priority
from project_friction.schemas.requests import StartAnalysisRequest
from project_friction.schemas.responses import (
    AnalysisRunStatusResponse,
    EvidenceResponse,
    FrictionReportResponse,
    IndicatorResponse,
    MetricResponse,
    RepositorySchema,
)
from project_friction.workflows.builder import build_friction_workflow_definition

router = APIRouter(prefix="/api/v1/friction", tags=["Project Friction"])


def calculate_progress(run: FrictionAnalysisRun, db: Session) -> tuple[int, str]:
    if run.status == "COMPLETED":
        return 100, "Completed"
    if run.status == "FAILED":
        return 100, "Failed"

    if not run.workflow_id:
        return 0, "Initializing"

    tasks = db.query(Task).filter(Task.workflow_id == run.workflow_id).order_by(Task.id).all()
    if not tasks:
        return 10, "Pending"

    completed = sum(1 for t in tasks if t.status == "SUCCESS")
    total = len(tasks)

    # Active task stage
    active = next((t for t in tasks if t.status == "PROCESSING"), None)
    stage_name = run.status.capitalize()
    if active:
        if active.type == "friction_init":
            stage_name = "Initializing Run"
        elif active.type == "friction_collect_github":
            stage_name = "Collecting Repository Data"
        elif active.type == "friction_calc_metrics":
            stage_name = "Calculating Workflow Metrics"
        elif active.type == "friction_generate_report":
            stage_name = "Evaluating Friction Score & Report"

    progress = int((completed / total) * 100) if total > 0 else 10
    return max(5, min(99, progress)), stage_name


@router.post("/analyses", status_code=202)
def start_friction_analysis(
    req: StartAnalysisRequest,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    owner = req.owner.strip()
    name = req.name.strip()
    full_name = f"{owner}/{name}".lower()
    user_id = current_user.id if current_user else None

    # Get or create repository scoped to current user
    repo_query = db.query(Repository).filter(Repository.full_name == full_name)
    if user_id is not None:
        repo_query = repo_query.filter(Repository.user_id == user_id)
    else:
        repo_query = repo_query.filter(Repository.user_id.is_(None))
    repo = repo_query.first()

    if not repo:
        repo = Repository(user_id=user_id, owner=owner, name=name, full_name=full_name, default_branch="main")
        db.add(repo)
        db.commit()
        db.refresh(repo)

    run_id = str(uuid4())

    # Build DAG workflow definition
    wf_def = build_friction_workflow_definition(
        run_id=run_id,
        owner=owner,
        name=name,
        time_window_days=req.time_window_days,
        github_token=req.github_token,
        user_id=user_id,
    )

    # Convert to WorkerGrid Workflow
    workflow_id = str(uuid4())
    key_to_id = {}
    now = utcnow_naive()

    # Step A: Insert tasks into PostgreSQL with user_id
    for item in wf_def["tasks"]:
        task = Task(
            user_id=user_id,
            type=item["type"],
            payload=item["payload"],
            status="WAITING" if item["depends_on"] else "PENDING",
            priority=normalize_priority(item["priority"]),
            max_retries=item["max_retries"],
            required_capability=item["required_capability"],
            workflow_id=workflow_id,
            workflow_key=item["key"],
            created_at=now,
            depends_on=[],
        )
        db.add(task)
        db.flush()
        key_to_id[item["key"]] = task.id

    # Step B: Link dependencies
    for item in wf_def["tasks"]:
        task = db.query(Task).filter(Task.workflow_id == workflow_id, Task.workflow_key == item["key"]).first()
        if task:
            task.depends_on = [key_to_id[dep] for dep in item["depends_on"] if dep in key_to_id]

    # Step C: Create FrictionAnalysisRun with user_id
    run = FrictionAnalysisRun(
        id=run_id,
        user_id=user_id,
        repository_id=repo.id,
        workflow_id=workflow_id,
        status="PENDING",
        time_window_days=req.time_window_days,
    )
    db.add(run)
    db.commit()

    # Step D: Enqueue ready PENDING tasks to Redis
    tasks = db.query(Task).filter(Task.workflow_id == workflow_id).all()
    for t in tasks:
        if t.status == "PENDING":
            enqueue_task(t.id, t.priority)

    return {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "repository": full_name,
        "status": "PENDING",
        "message": "Project Friction analysis scheduled",
    }


@router.get("/analyses")
def list_friction_analyses(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(FrictionAnalysisRun)
    if current_user:
        query = query.filter(FrictionAnalysisRun.user_id == current_user.id)
    else:
        query = query.filter(FrictionAnalysisRun.user_id.is_(None))

    runs = query.order_by(FrictionAnalysisRun.created_at.desc()).limit(limit).all()
    res = []
    for r in runs:
        prog, stage = calculate_progress(r, db)
        res.append({
            "run_id": r.id,
            "repository": r.repository.full_name if r.repository else "unknown",
            "status": r.status,
            "progress_pct": prog,
            "current_stage": stage,
            "overall_friction_score": r.overall_friction_score,
            "friction_level": r.friction_level,
            "created_at": r.created_at,
        })
    return {"items": res, "count": len(res)}


@router.get("/analyses/{run_id}", response_model=AnalysisRunStatusResponse)
def get_friction_analysis_status(
    run_id: str,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id)
    if current_user:
        query = query.filter(FrictionAnalysisRun.user_id == current_user.id)
    else:
        query = query.filter(FrictionAnalysisRun.user_id.is_(None))

    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    prog, stage = calculate_progress(run, db)

    # Check workflow tasks for failure
    if run.workflow_id and run.status not in ("COMPLETED", "FAILED"):
        wf_tasks = db.query(Task).filter(Task.workflow_id == run.workflow_id).all()
        if any(t.status == "FAILED" for t in wf_tasks):
            run.status = "FAILED"
            failed_task = next((t for t in wf_tasks if t.status == "FAILED"), None)
            run.error_message = failed_task.last_error if failed_task else "Workflow failed"
            db.commit()

    return AnalysisRunStatusResponse(
        run_id=run.id,
        repository=run.repository.full_name if run.repository else "unknown",
        status=run.status,
        progress_pct=prog,
        current_stage=stage,
        time_window_days=run.time_window_days,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


@router.get("/analyses/{run_id}/report", response_model=FrictionReportResponse)
def get_friction_report(
    run_id: str,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id)
    if current_user:
        query = query.filter(FrictionAnalysisRun.user_id == current_user.id)
    else:
        query = query.filter(FrictionAnalysisRun.user_id.is_(None))

    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    metrics_records = db.query(FrictionMetric).filter(FrictionMetric.run_id == run_id).all()
    indicators_records = db.query(FrictionIndicator).filter(FrictionIndicator.run_id == run_id).all()

    # Group metrics
    metrics_list = [
        MetricResponse(
            category=m.metric_category,
            name=m.metric_name,
            value=m.metric_value,
            unit=m.unit,
            details=m.details,
        )
        for m in metrics_records
    ]

    # Calculate dimension scores
    dimensions = {}
    for cat in ("code_review", "ci_cd", "backlog", "velocity"):
        cat_metrics = [m for m in metrics_list if m.category == cat or (cat == "backlog" and m.category in ("backlog", "staleness"))]
        if cat_metrics:
            dimensions[cat] = round(sum(m.value for m in cat_metrics) / len(cat_metrics), 1)

    indicators_list = []
    for ind in indicators_records:
        evidence_records = db.query(FrictionEvidence).filter(FrictionEvidence.indicator_id == ind.id).all()
        ev_items = [
            EvidenceResponse(
                id=ev.id,
                entity_type=ev.entity_type,
                external_id=ev.external_id,
                title=ev.title,
                url=ev.url,
                metrics_breakdown=ev.metrics_breakdown,
            )
            for ev in evidence_records
        ]
        indicators_list.append(
            IndicatorResponse(
                id=ind.id,
                category=ind.category,
                severity=ind.severity,
                title=ind.title,
                summary=ind.summary,
                score_impact=ind.score_impact,
                recommendation=ind.recommendation,
                evidence=ev_items,
            )
        )

    return FrictionReportResponse(
        run_id=run.id,
        repository=run.repository.full_name if run.repository else "unknown",
        status=run.status,
        time_window_days=run.time_window_days,
        overall_friction_score=run.overall_friction_score,
        friction_level=run.friction_level,
        completed_at=run.completed_at,
        dimensions=dimensions,
        metrics=metrics_list,
        indicators=indicators_list,
    )


@router.get("/indicators/{indicator_id}/evidence")
def get_indicator_evidence(
    indicator_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(FrictionIndicator).filter(FrictionIndicator.id == indicator_id)
    if current_user:
        query = query.filter(FrictionIndicator.user_id == current_user.id)
    else:
        query = query.filter(FrictionIndicator.user_id.is_(None))

    indicator = query.first()
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicator not found")

    evidence = db.query(FrictionEvidence).filter(FrictionEvidence.indicator_id == indicator_id).all()
    return {
        "indicator_id": indicator_id,
        "title": indicator.title,
        "severity": indicator.severity,
        "count": len(evidence),
        "items": [
            {
                "id": ev.id,
                "entity_type": ev.entity_type,
                "external_id": ev.external_id,
                "title": ev.title,
                "url": ev.url,
                "metrics_breakdown": ev.metrics_breakdown,
            }
            for ev in evidence
        ],
    }


@router.get("/repositories")
def list_analyzed_repositories(
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Repository)
    if current_user:
        query = query.filter(Repository.user_id == current_user.id)
    else:
        query = query.filter(Repository.user_id.is_(None))

    repos = query.order_by(Repository.full_name).all()
    items = []
    for r in repos:
        latest_run = (
            db.query(FrictionAnalysisRun)
            .filter(FrictionAnalysisRun.repository_id == r.id, FrictionAnalysisRun.status == "COMPLETED")
            .order_by(FrictionAnalysisRun.completed_at.desc())
            .first()
        )
        items.append({
            "id": r.id,
            "owner": r.owner,
            "name": r.name,
            "full_name": r.full_name,
            "default_branch": r.default_branch,
            "latest_score": latest_run.overall_friction_score if latest_run else None,
            "latest_level": latest_run.friction_level if latest_run else None,
            "last_analyzed_at": latest_run.completed_at if latest_run else None,
        })
    return {"items": items, "count": len(items)}


@router.get("/github/user-repositories")
def list_user_github_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gh_account = db.query(UserGitHubAccount).filter(UserGitHubAccount.user_id == current_user.id).first()
    if not gh_account or not gh_account.encrypted_access_token:
        raise HTTPException(status_code=400, detail="No GitHub account connected")

    try:
        token = decrypt_token(gh_account.encrypted_access_token)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt GitHub authorization token: {err}")

    # Fetch user repos from GitHub REST API
    url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "WorkerGrid-OAuth/1.0",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"Failed to fetch repositories from GitHub API: {err}")

    repos = [
        {
            "id": repo.get("id"),
            "owner": repo.get("owner", {}).get("login"),
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "private": repo.get("private", False),
            "default_branch": repo.get("default_branch", "main"),
            "html_url": repo.get("html_url"),
        }
        for repo in data
        if isinstance(repo, dict)
    ]
    return {"items": repos, "count": len(repos)}

