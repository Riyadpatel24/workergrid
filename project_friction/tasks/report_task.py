from typing import Any
from sqlalchemy.orm import Session
from app.core.time import utcnow_naive
from app.models.friction import (
    FrictionAnalysisRun,
    FrictionEvidence,
    FrictionIndicator,
    FrictionMetric,
    FrictionRawSnapshot,
)
from project_friction.analysis import evaluate_friction_indicators


def handle_friction_generate_report(db: Session, payload: dict[str, Any]):
    run_id = payload["run_id"]
    print(f"[TaskHandler] Generating friction report for run {run_id}...")

    # Load metrics & raw snapshots
    metrics_records = db.query(FrictionMetric).filter(FrictionMetric.run_id == run_id).all()
    snapshots = db.query(FrictionRawSnapshot).filter(FrictionRawSnapshot.run_id == run_id).all()

    metrics = [
        {"category": m.metric_category, "name": m.metric_name, "value": m.metric_value, "unit": m.unit, "details": m.details}
        for m in metrics_records
    ]
    raw_list = [
        {"entity_type": s.entity_type, "external_id": s.external_id, "snapshot_data": s.snapshot_data}
        for s in snapshots
    ]

    dimensions, overall_score, friction_level, indicators_data = evaluate_friction_indicators(metrics, raw_list)

    run_record = db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id).first()
    user_id = run_record.user_id if run_record else payload.get("user_id")

    # Save indicators & evidence
    for ind in indicators_data:
        indicator_record = FrictionIndicator(
            user_id=user_id,
            run_id=run_id,
            category=ind["category"],
            severity=ind["severity"],
            title=ind["title"],
            summary=ind["summary"],
            score_impact=ind.get("score_impact", 0.0),
            recommendation=ind.get("recommendation"),
        )
        db.add(indicator_record)
        db.flush()

        for ev in ind.get("evidence", []):
            ev_record = FrictionEvidence(
                user_id=user_id,
                indicator_id=indicator_record.id,
                run_id=run_id,
                entity_type=ev.get("entity_type"),
                external_id=ev.get("external_id"),
                title=ev.get("title"),
                url=ev.get("url"),
                metrics_breakdown=ev.get("metrics_breakdown"),
            )
            db.add(ev_record)

    # Update run state
    if run_record:

        run_record.overall_friction_score = overall_score
        run_record.friction_level = friction_level
        run_record.status = "COMPLETED"
        run_record.completed_at = utcnow_naive()

    db.commit()
    print(f"[TaskHandler] friction_generate_report completed for run {run_id} (Score: {overall_score}, Level: {friction_level})")
