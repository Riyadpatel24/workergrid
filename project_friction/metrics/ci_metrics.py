from typing import Any


def calculate_ci_metrics(ci_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ci_runs:
        return [
            {"category": "ci_cd", "name": "ci_failure_rate_pct", "value": 0.0, "unit": "percent", "details": {"total_runs": 0}},
        ]

    total_runs = len(ci_runs)
    failed_runs = sum(1 for r in ci_runs if r.get("conclusion") == "failure")
    successful_runs = sum(1 for r in ci_runs if r.get("conclusion") == "success")

    failure_rate = round((failed_runs / total_runs) * 100.0, 1) if total_runs > 0 else 0.0

    return [
        {
            "category": "ci_cd",
            "name": "ci_failure_rate_pct",
            "value": failure_rate,
            "unit": "percent",
            "details": {
                "total_runs": total_runs,
                "failed_runs": failed_runs,
                "successful_runs": successful_runs,
            },
        },
    ]
