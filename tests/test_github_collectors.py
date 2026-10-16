import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.friction import FrictionAnalysisRun, FrictionRawSnapshot, Repository
from project_friction.collectors.github import (
    GitHubClient,
    GitHubPRCollector,
    GitHubCICollector,
    GitHubIssueCollector,
    RateLimitExceededError,
)
from project_friction.tasks.collect_task import handle_friction_collect_github, handle_friction_init
from project_friction.analysis.engine import evaluate_friction_indicators


class TestGitHubCollectors(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_pr_collection_without_review_exhaustion(self):
        """Verify fetch_reviews_max prevents excessive N+1 review API calls."""
        client = MagicMock(spec=GitHubClient)
        from app.core.time import utcnow_naive
        now_iso = utcnow_naive().strftime("%Y-%m-%dT%H:%M:%SZ")
        # Mock 10 PRs
        mock_prs = [
            {
                "number": i,
                "title": f"PR {i}",
                "state": "open",
                "user": {"login": f"user{i}"},
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            for i in range(1, 11)
        ]
        client.get.return_value = (mock_prs, {})

        collector = GitHubPRCollector(client)
        result = collector.fetch_pull_requests("owner", "repo", days=30, max_items=10, fetch_reviews_max=2)

        self.assertEqual(len(result), 10)
        # 1 call for pulls list + 2 calls for reviews = 3 total get calls
        self.assertEqual(client.get.call_count, 3)

    def test_review_fetch_failure_does_not_destroy_pr_collection(self):
        """Verify that failure during review fetch does not break PR collection."""
        from app.core.time import utcnow_naive
        now_iso = utcnow_naive().strftime("%Y-%m-%dT%H:%M:%SZ")
        client = MagicMock(spec=GitHubClient)
        mock_prs = [
            {
                "number": 1,
                "title": "PR 1",
                "state": "open",
                "user": {"login": "user1"},
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        ]


        def side_effect(endpoint, params=None):
            if "reviews" in endpoint:
                raise RuntimeError("Reviews endpoint error")
            return mock_prs, {}

        client.get.side_effect = side_effect

        collector = GitHubPRCollector(client)
        result = collector.fetch_pull_requests("owner", "repo", days=30, max_items=10, fetch_reviews_max=2)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["number"], 1)
        self.assertIsNone(result[0]["first_review_at"])

    def test_issue_since_timestamp_formatting(self):
        """Verify since parameter is formatted in UTC Z format."""
        client = MagicMock(spec=GitHubClient)
        client.get.return_value = ([], {})

        collector = GitHubIssueCollector(client)
        collector.fetch_issues("owner", "repo", days=30)

        client.get.assert_called_once()
        args, kwargs = client.get.call_args
        endpoint, params = args[0], args[1]
        self.assertIn("since", params)
        since_val = params["since"]
        self.assertTrue(since_val.endswith("Z"))
        self.assertNotIn("+00:00", since_val)

    def test_rate_limit_errors_surfaced_correctly(self):
        """Verify RateLimitExceededError is surfaced and fails the task run."""
        client = MagicMock(spec=GitHubClient)
        client.get.side_effect = RateLimitExceededError(1700000000, "Rate limit hit")

        run_id = "test-rate-limit-run"
        handle_friction_init(self.db, {"run_id": run_id, "owner": "owner", "name": "repo"})

        original_get = GitHubClient.get
        try:
            GitHubClient.get = MagicMock(side_effect=RateLimitExceededError(1700000000, "Rate limit hit"))

            collector_pr = GitHubPRCollector(client)
            collector_ci = GitHubCICollector(client)
            collector_issue = GitHubIssueCollector(client)

            # Test collectors directly raise RateLimitExceededError
            with self.assertRaises(RateLimitExceededError):
                collector_pr.fetch_pull_requests("owner", "repo")
            with self.assertRaises(RateLimitExceededError):
                collector_ci.fetch_ci_runs("owner", "repo")
            with self.assertRaises(RateLimitExceededError):
                collector_issue.fetch_issues("owner", "repo")

            # Test task handler fails task run
            with self.assertRaises(RuntimeError) as ctx:
                handle_friction_collect_github(self.db, {
                    "run_id": run_id,
                    "owner": "owner",
                    "name": "repo",
                    "github_token": "invalid_or_rate_limited",
                })

            self.assertIn("GitHub API collection failed", str(ctx.exception))
            run_record = self.db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id).first()
            self.assertEqual(run_record.status, "FAILED")
            self.assertIn("rate limit", run_record.error_message.lower())
        finally:
            GitHubClient.get = original_get


    def test_genuinely_empty_repo_produces_insufficient_data(self):
        """Verify zero-activity repositories still yield INSUFFICIENT_DATA status."""
        dims, overall_score, friction_level, indicators = evaluate_friction_indicators(
            metrics=[],
            raw_snapshots=[],
        )
        self.assertIsNone(overall_score)
        self.assertEqual(friction_level, "INSUFFICIENT_DATA")
        self.assertEqual(len(indicators), 1)
        self.assertEqual(indicators[0]["severity"], "INSUFFICIENT_DATA")


if __name__ == "__main__":
    unittest.main()
