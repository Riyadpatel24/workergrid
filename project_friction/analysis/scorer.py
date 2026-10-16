from typing import Any


def compute_dimension_scores(metrics: list[dict[str, Any]]) -> dict[str, float]:
    metrics_map = {m["name"]: m["value"] for m in metrics}

    # Review latency dimension (0 - 100)
    rev_lat = metrics_map.get("avg_review_latency_hours", 0.0)
    if rev_lat <= 12:
        s_review = (rev_lat / 12.0) * 20.0
    elif rev_lat <= 48:
        s_review = 20.0 + ((rev_lat - 12.0) / 36.0) * 50.0
    else:
        s_review = min(100.0, 70.0 + ((rev_lat - 48.0) / 48.0) * 30.0)

    # CI Failure rate dimension (0 - 100)
    ci_fail = metrics_map.get("ci_failure_rate_pct", 0.0)
    if ci_fail <= 5:
        s_ci = (ci_fail / 5.0) * 20.0
    elif ci_fail <= 25:
        s_ci = 20.0 + ((ci_fail - 5.0) / 20.0) * 50.0
    else:
        s_ci = min(100.0, 70.0 + ((ci_fail - 25.0) / 25.0) * 30.0)

    # Stale PR ratio dimension (0 - 100)
    stale_pr = metrics_map.get("stale_pr_ratio_pct", 0.0)
    if stale_pr <= 10:
        s_stale = (stale_pr / 10.0) * 20.0
    elif stale_pr <= 30:
        s_stale = 20.0 + ((stale_pr - 10.0) / 20.0) * 50.0
    else:
        s_stale = min(100.0, 70.0 + ((stale_pr - 30.0) / 30.0) * 30.0)

    # Time-to-merge dimension (0 - 100)
    merge_time = metrics_map.get("avg_time_to_merge_hours", 0.0)
    if merge_time <= 24:
        s_merge = (merge_time / 24.0) * 20.0
    elif merge_time <= 72:
        s_merge = 20.0 + ((merge_time - 24.0) / 48.0) * 50.0
    else:
        s_merge = min(100.0, 70.0 + ((merge_time - 72.0) / 72.0) * 30.0)

    return {
        "code_review": round(s_review, 1),
        "ci_cd": round(s_ci, 1),
        "backlog_staleness": round(s_stale, 1),
        "delivery_velocity": round(s_merge, 1),
    }


def compute_overall_friction_score(dimensions: dict[str, float]) -> tuple[float, str]:
    w_review = 0.35
    w_ci = 0.25
    w_stale = 0.20
    w_velocity = 0.20

    score = (
        w_review * dimensions.get("code_review", 0.0)
        + w_ci * dimensions.get("ci_cd", 0.0)
        + w_stale * dimensions.get("backlog_staleness", 0.0)
        + w_velocity * dimensions.get("delivery_velocity", 0.0)
    )
    overall_score = round(min(100.0, max(0.0, score)), 1)

    if overall_score <= 25.0:
        level = "LOW"
    elif overall_score <= 55.0:
        level = "MEDIUM"
    elif overall_score <= 75.0:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return overall_score, level
