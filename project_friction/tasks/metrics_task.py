from typing import Any
from sqlalchemy.orm import Session
from app.models.friction import FrictionAnalysisRun, FrictionMetric, FrictionRawSnapshot
from project_friction.metrics import (
    calculate_backlog_metrics,
    calculate_ci_metrics,
    calculate_pr_metrics,
)


def handle_friction_calc_metrics(db: Session, payload: dict[str, Any]):
    run_id = payload["run_id"]
    print(f"[TaskHandler] Calculating metrics for run {run_id}...")

    # Load raw snapshots
    snapshots = db.query(FrictionRawSnapshot).filter(FrictionRawSnapshot.run_id == run_id).all()

    prs = [s.snapshot_data for s in snapshots if s.entity_type == "pull_request" and s.snapshot_data]
    ci_runs = [s.snapshot_data for s in snapshots if s.entity_type == "workflow_run" and s.snapshot_data]
    issues = [s.snapshot_data for s in snapshots if s.entity_type == "issue" and s.snapshot_data]

    # Calculate metrics
    pr_metrics = calculate_pr_metrics(prs)
    ci_metrics = calculate_ci_metrics(ci_runs)
    backlog_metrics = calculate_backlog_metrics(issues)

    all_calculated = pr_metrics + ci_metrics + backlog_metrics

    run_record = db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id).first()
    user_id = run_record.user_id if run_record else payload.get("user_id")

    # Save to DB
    for m in all_calculated:
        metric_record = FrictionMetric(
            user_id=user_id,
            run_id=run_id,
            metric_category=m["category"],
            metric_name=m["name"],
            metric_value=m["value"],
            unit=m.get("unit"),
            details=m.get("details"),
        )
        db.add(metric_record)

    if run_record:
        run_record.status = "ANALYZING"


    db.commit()
    print(f"[TaskHandler] friction_calc_metrics completed for run {run_id} ({len(all_calculated)} metrics saved)")
