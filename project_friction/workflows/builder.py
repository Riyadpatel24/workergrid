from typing import Any


def build_friction_workflow_definition(
    run_id: str,
    owner: str,
    name: str,
    time_window_days: int = 30,
    github_token: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    common_payload = {
        "run_id": run_id,
        "owner": owner,
        "name": name,
        "time_window_days": time_window_days,
        "user_id": user_id,
    }


    workflow_name = f"ProjectFriction_{owner}_{name}_{run_id[:8]}"

    tasks = [
        {
            "key": "step1_init",
            "type": "friction_init",
            "payload": common_payload,
            "priority": "HIGH",
            "depends_on": [],
            "required_capability": "friction",
            "max_retries": 3,
        },
        {
            "key": "step2_collect",
            "type": "friction_collect_github",
            "payload": common_payload,
            "priority": "MEDIUM",
            "depends_on": ["step1_init"],
            "required_capability": "github",
            "max_retries": 3,
        },
        {
            "key": "step3_metrics",
            "type": "friction_calc_metrics",
            "payload": common_payload,
            "priority": "MEDIUM",
            "depends_on": ["step2_collect"],
            "required_capability": "friction",
            "max_retries": 3,
        },
        {
            "key": "step4_report",
            "type": "friction_generate_report",
            "payload": common_payload,
            "priority": "HIGH",
            "depends_on": ["step3_metrics"],
            "required_capability": "friction",
            "max_retries": 3,
        },
    ]

    return {
        "name": workflow_name,
        "tasks": tasks,
    }
