import unittest
from project_friction.analysis.scorer import compute_dimension_scores, compute_overall_friction_score
from project_friction.analysis.engine import evaluate_friction_indicators


class TestFrictionScorer(unittest.TestCase):
    def test_scorer_healthy_repo(self):
        metrics = [
            {"name": "avg_review_latency_hours", "value": 6.0},
            {"name": "ci_failure_rate_pct", "value": 2.0},
            {"name": "stale_pr_ratio_pct", "value": 5.0},
            {"name": "avg_time_to_merge_hours", "value": 12.0},
        ]

        dims = compute_dimension_scores(metrics)
        score, level = compute_overall_friction_score(dims)

        self.assertLess(score, 25.0)
        self.assertEqual(level, "LOW")

    def test_scorer_high_friction_repo(self):
        metrics = [
            {"name": "avg_review_latency_hours", "value": 72.0},
            {"name": "ci_failure_rate_pct", "value": 35.0},
            {"name": "stale_pr_ratio_pct", "value": 40.0},
            {"name": "avg_time_to_merge_hours", "value": 96.0},
        ]

        dims = compute_dimension_scores(metrics)
        score, level = compute_overall_friction_score(dims)

        self.assertGreater(score, 70.0)
        self.assertIn(level, ("HIGH", "CRITICAL"))

    def test_evaluate_friction_indicators(self):
        metrics = [
            {"name": "avg_review_latency_hours", "value": 30.0},
            {"name": "ci_failure_rate_pct", "value": 25.0},
            {"name": "stale_pr_ratio_pct", "value": 20.0},
            {"name": "avg_time_to_merge_hours", "value": 48.0},
        ]
        raw_snapshots = [
            {
                "entity_type": "pull_request",
                "snapshot_data": {
                    "number": 101,
                    "title": "Slow review PR",
                    "created_at": "2026-08-01T10:00:00Z",
                    "html_url": "https://github.com/test/repo/pull/101",
                    "state": "open",
                },
            }
        ]

        dims, score, level, indicators = evaluate_friction_indicators(metrics, raw_snapshots)

        self.assertGreaterEqual(len(indicators), 2)
        titles = [i["title"] for i in indicators]
        self.assertTrue(any("Review Latency" in t for t in titles))
        self.assertTrue(any("CI Failure" in t for t in titles))


if __name__ == "__main__":
    unittest.main()
