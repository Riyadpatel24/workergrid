from datetime import datetime, timezone
from typing import Any
from project_friction.metrics.base import calculate_percentile, hours_between, parse_iso


def calculate_pr_metrics(prs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = []
    if not prs:
        return [
            {"category": "code_review", "name": "avg_review_latency_hours", "value": 0.0, "unit": "hours", "details": {"count": 0}},
            {"category": "code_review", "name": "stale_pr_ratio_pct", "value": 0.0, "unit": "percent", "details": {"count": 0}},
            {"category": "velocity", "name": "avg_time_to_merge_hours", "value": 0.0, "unit": "hours", "details": {"count": 0}},
        ]

    review_latencies = []
    merge_times = []
    stale_count = 0
    now = datetime.now(timezone.utc)

    for pr in prs:
        created_at = pr.get("created_at")
        first_review_at = pr.get("first_review_at")
        merged_at = pr.get("merged_at")
        state = pr.get("state")
        updated_at = parse_iso(pr.get("updated_at"))

        # Review latency
        if first_review_at and created_at:
            lat = hours_between(created_at, first_review_at)
            if lat is not None:
                review_latencies.append(lat)

        # Merge time (lead time)
        if merged_at and created_at:
            m_time = hours_between(created_at, merged_at)
            if m_time is not None:
                merge_times.append(m_time)

        # Stale PR check (open for > 7 days without recent update)
        if state == "open" and updated_at:
            days_inactive = (now - updated_at).total_seconds() / 86400.0
            if days_inactive > 7:
                stale_count += 1

    avg_review_lat = round(sum(review_latencies) / len(review_latencies), 2) if review_latencies else 0.0
    p95_review_lat = calculate_percentile(review_latencies, 95)

    avg_merge_time = round(sum(merge_times) / len(merge_times), 2) if merge_times else 0.0
    p95_merge_time = calculate_percentile(merge_times, 95)

    open_prs = [p for p in prs if p.get("state") == "open"]
    stale_ratio = round((stale_count / len(open_prs)) * 100.0, 1) if open_prs else 0.0

    metrics.extend([
        {
            "category": "code_review",
            "name": "avg_review_latency_hours",
            "value": avg_review_lat,
            "unit": "hours",
            "details": {"p95": p95_review_lat, "samples": len(review_latencies)},
        },
        {
            "category": "code_review",
            "name": "stale_pr_ratio_pct",
            "value": stale_ratio,
            "unit": "percent",
            "details": {"stale_prs": stale_count, "open_prs": len(open_prs)},
        },
        {
            "category": "velocity",
            "name": "avg_time_to_merge_hours",
            "value": avg_merge_time,
            "unit": "hours",
            "details": {"p95": p95_merge_time, "merged_count": len(merge_times)},
        },
    ])
    return metrics
