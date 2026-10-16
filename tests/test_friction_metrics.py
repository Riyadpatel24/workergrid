import unittest
from project_friction.metrics.pr_metrics import calculate_pr_metrics
from project_friction.metrics.ci_metrics import calculate_ci_metrics
from project_friction.metrics.backlog_metrics import calculate_backlog_metrics


class TestFrictionMetrics(unittest.TestCase):
    def test_calculate_pr_metrics(self):
        sample_prs = [
            {
                "number": 1,
                "created_at": "2026-08-01T10:00:00Z",
                "first_review_at": "2026-08-01T22:00:00Z",  # 12h
                "merged_at": "2026-08-02T10:00:00Z",        # 24h
                "state": "closed",
            },
            {
                "number": 2,
                "created_at": "2026-08-01T10:00:00Z",
                "first_review_at": "2026-08-02T10:00:00Z",  # 24h
                "merged_at": "2026-08-03T10:00:00Z",        # 48h
                "state": "closed",
            },
        ]

        metrics = calculate_pr_metrics(sample_prs)
        metrics_map = {m["name"]: m["value"] for m in metrics}

        self.assertEqual(metrics_map["avg_review_latency_hours"], 18.0)
        self.assertEqual(metrics_map["avg_time_to_merge_hours"], 36.0)
        self.assertEqual(metrics_map["stale_pr_ratio_pct"], 0.0)

    def test_calculate_ci_metrics(self):
        sample_runs = [
            {"id": 101, "conclusion": "success"},
            {"id": 102, "conclusion": "success"},
            {"id": 103, "conclusion": "failure"},
            {"id": 104, "conclusion": "success"},
        ]

        metrics = calculate_ci_metrics(sample_runs)
        metrics_map = {m["name"]: m["value"] for m in metrics}

        self.assertEqual(metrics_map["ci_failure_rate_pct"], 25.0)

    def test_calculate_backlog_metrics(self):
        sample_issues = [
            {"number": 10, "state": "closed", "created_at": "2026-08-01T10:00:00Z", "closed_at": "2026-08-02T10:00:00Z"},
            {"number": 11, "state": "open", "comments_count": 0},
        ]

        metrics = calculate_backlog_metrics(sample_issues)
        metrics_map = {m["name"]: m["value"] for m in metrics}

        self.assertEqual(metrics_map["avg_issue_close_time_hours"], 24.0)
        self.assertEqual(metrics_map["stale_issue_ratio_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
