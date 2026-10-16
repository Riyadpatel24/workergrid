from typing import Any
from project_friction.metrics.base import hours_between


def calculate_backlog_metrics(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not issues:
        return [
            {"category": "backlog", "name": "avg_issue_close_time_hours", "value": 0.0, "unit": "hours", "details": {"closed_count": 0}},
            {"category": "backlog", "name": "stale_issue_ratio_pct", "value": 0.0, "unit": "percent", "details": {"open_issues": 0}},
        ]

    close_times = []
    stale_issues = 0
    open_issues = [i for i in issues if i.get("state") == "open"]

    for issue in issues:
        created_at = issue.get("created_at")
        closed_at = issue.get("closed_at")

        if closed_at and created_at:
            dur = hours_between(created_at, closed_at)
            if dur is not None:
                close_times.append(dur)

        if issue.get("state") == "open" and issue.get("comments_count", 0) == 0:
            stale_issues += 1

    avg_close_time = round(sum(close_times) / len(close_times), 2) if close_times else 0.0
    stale_ratio = round((stale_issues / len(open_issues)) * 100.0, 1) if open_issues else 0.0

    return [
        {
            "category": "backlog",
            "name": "avg_issue_close_time_hours",
            "value": avg_close_time,
            "unit": "hours",
            "details": {"closed_count": len(close_times)},
        },
        {
            "category": "backlog",
            "name": "stale_issue_ratio_pct",
            "value": stale_ratio,
            "unit": "percent",
            "details": {"uncommented_open_issues": stale_issues, "open_issues": len(open_issues)},
        },
    ]
