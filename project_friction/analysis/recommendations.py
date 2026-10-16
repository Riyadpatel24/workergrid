def generate_recommendations(category: str, metric_name: str, metric_value: float) -> str:
    if metric_name == "avg_review_latency_hours" and metric_value > 24:
        return "Establish automatic reviewer rotation and set a team target of first review under 24 hours."
    if metric_name == "stale_pr_ratio_pct" and metric_value > 20:
        return "Implement automated stale PR bot to ping authors/reviewers after 5 days of inactivity."
    if metric_name == "ci_failure_rate_pct" and metric_value > 15:
        return "Investigate flaky CI tests and quarantine non-deterministic test suites to unblock deployment pipeline."
    if metric_name == "avg_time_to_merge_hours" and metric_value > 48:
        return "Decompose large Pull Requests into smaller, single-purpose branches to accelerate review cycles."
    if metric_name == "stale_issue_ratio_pct" and metric_value > 30:
        return "Triage open issue backlog and add issue templates with required reproduction steps."
    return "Maintain current workflow parameters and monitor weekly trend metrics."
