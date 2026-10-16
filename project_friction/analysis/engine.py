from typing import Any
from project_friction.analysis.recommendations import generate_recommendations
from project_friction.analysis.scorer import compute_dimension_scores, compute_overall_friction_score


def evaluate_friction_indicators(
    metrics: list[dict[str, Any]],
    raw_snapshots: list[dict[str, Any]],
) -> tuple[dict[str, float], float | None, str, list[dict[str, Any]]]:
    # Check if zero activity was fetched
    if not raw_snapshots or len(raw_snapshots) == 0:
        dimensions = {
            "code_review": 0.0,
            "ci_cd": 0.0,
            "backlog_staleness": 0.0,
            "delivery_velocity": 0.0,
        }
        indicators = [
            {
                "category": "workflow",
                "severity": "INSUFFICIENT_DATA",
                "title": "INSUFFICIENT ACTIVITY",
                "summary": "No PR, CI, or issue activity was found in the selected period. Run the analysis over a longer period for meaningful friction metrics.",
                "score_impact": 0.0,
                "recommendation": "Select a longer time window (e.g., 90 days) or choose a repository with recent pull request or CI activity.",
                "evidence": [],
            }
        ]
        return dimensions, None, "INSUFFICIENT_DATA", indicators

    dimensions = compute_dimension_scores(metrics)
    overall_score, friction_level = compute_overall_friction_score(dimensions)
    indicators = []

    metrics_map = {m["name"]: m for m in metrics}

    # 1. Review Latency Indicator
    rev_lat = metrics_map.get("avg_review_latency_hours", {})
    if rev_lat and rev_lat.get("value", 0) > 18:
        val = rev_lat["value"]
        sev = "CRITICAL" if val > 48 else "HIGH" if val > 24 else "MEDIUM"
        ev_list = []
        for snap in raw_snapshots:
            if snap.get("entity_type") == "pull_request":
                d = snap.get("snapshot_data", {})
                if d.get("first_review_at") or d.get("state") == "open":
                    ev_list.append({
                        "entity_type": "pull_request",
                        "external_id": f"#{d.get('number')}",
                        "title": d.get("title", ""),
                        "url": d.get("html_url", ""),
                        "metrics_breakdown": {
                            "created_at": d.get("created_at"),
                            "first_review_at": d.get("first_review_at"),
                            "author": d.get("user_login"),
                        },
                    })
                    if len(ev_list) >= 5:
                        break

        indicators.append({
            "category": "code_review",
            "severity": sev,
            "title": f"High PR Review Latency ({val} hours)",
            "summary": f"Average time to receive first code review is {val} hours, exceeding the 18-hour healthy target.",
            "score_impact": round(dimensions["code_review"] * 0.35, 1),
            "recommendation": generate_recommendations("code_review", "avg_review_latency_hours", val),
            "evidence": ev_list,
        })

    # 2. CI Failure Rate Indicator
    ci_fail = metrics_map.get("ci_failure_rate_pct", {})
    if ci_fail and ci_fail.get("value", 0) > 12:
        val = ci_fail["value"]
        sev = "CRITICAL" if val > 30 else "HIGH" if val > 20 else "MEDIUM"
        ev_list = []
        for snap in raw_snapshots:
            if snap.get("entity_type") == "workflow_run":
                d = snap.get("snapshot_data", {})
                if d.get("conclusion") == "failure":
                    ev_list.append({
                        "entity_type": "workflow_run",
                        "external_id": f"Run #{d.get('run_number') or d.get('id')}",
                        "title": d.get("name", "Workflow Run"),
                        "url": d.get("html_url", ""),
                        "metrics_breakdown": {
                            "status": d.get("status"),
                            "conclusion": d.get("conclusion"),
                            "event": d.get("event"),
                        },
                    })
                    if len(ev_list) >= 5:
                        break

        indicators.append({
            "category": "ci_cd",
            "severity": sev,
            "title": f"Elevated CI Failure Rate ({val}%)",
            "summary": f"{val}% of automated CI workflow runs ended in failure, indicating build or test instability.",
            "score_impact": round(dimensions["ci_cd"] * 0.25, 1),
            "recommendation": generate_recommendations("ci_cd", "ci_failure_rate_pct", val),
            "evidence": ev_list,
        })

    # 3. Stale PR Ratio Indicator
    stale_pr = metrics_map.get("stale_pr_ratio_pct", {})
    if stale_pr and stale_pr.get("value", 0) > 15:
        val = stale_pr["value"]
        sev = "HIGH" if val > 35 else "MEDIUM"
        ev_list = []
        for snap in raw_snapshots:
            if snap.get("entity_type") == "pull_request":
                d = snap.get("snapshot_data", {})
                if d.get("state") == "open":
                    ev_list.append({
                        "entity_type": "pull_request",
                        "external_id": f"#{d.get('number')}",
                        "title": d.get("title", ""),
                        "url": d.get("html_url", ""),
                        "metrics_breakdown": {
                            "created_at": d.get("created_at"),
                            "updated_at": d.get("updated_at"),
                            "author": d.get("user_login"),
                        },
                    })
                    if len(ev_list) >= 5:
                        break

        indicators.append({
            "category": "backlog",
            "severity": sev,
            "title": f"Stale Pull Requests ({val}%)",
            "summary": f"{val}% of open pull requests have seen no activity for over 7 days.",
            "score_impact": round(dimensions["backlog_staleness"] * 0.20, 1),
            "recommendation": generate_recommendations("backlog", "stale_pr_ratio_pct", val),
            "evidence": ev_list,
        })

    # If no major friction issues detected on active data
    if not indicators:
        indicators.append({
            "category": "workflow",
            "severity": "LOW",
            "title": "Healthy Developer Workflow",
            "summary": "Repository metrics indicate smooth code review throughput and build stability.",
            "score_impact": 0.0,
            "recommendation": "Continue monitoring workflow metrics periodically.",
            "evidence": [],
        })

    return dimensions, overall_score, friction_level, indicators
