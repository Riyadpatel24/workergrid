from typing import Any, Callable
from sqlalchemy.orm import Session
from project_friction.tasks.collect_task import handle_friction_collect_github, handle_friction_init
from project_friction.tasks.metrics_task import handle_friction_calc_metrics
from project_friction.tasks.report_task import handle_friction_generate_report

TASK_HANDLERS: dict[str, Callable[[Session, dict[str, Any]], None]] = {
    "friction_init": handle_friction_init,
    "friction_collect_github": handle_friction_collect_github,
    "friction_calc_metrics": handle_friction_calc_metrics,
    "friction_generate_report": handle_friction_generate_report,
}


def dispatch_task(task_type: str, db: Session, payload: dict[str, Any]) -> bool:
    handler = TASK_HANDLERS.get(task_type)
    if handler:
        handler(db, payload)
        return True
    return False
