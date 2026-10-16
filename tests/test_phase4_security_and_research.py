import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_oauth_state,
    create_refresh_token,
    decrypt_token,
    encrypt_token,
    get_password_hash,
    verify_oauth_state,
)
from app.db.database import Base
from app.models.friction import FrictionAnalysisRun, Repository
from app.models.task import Task
from app.models.user import User, UserGitHubAccount
from main import app
from project_friction.analysis.engine import evaluate_friction_indicators
from project_friction.analysis.scorer import compute_dimension_scores, compute_overall_friction_score
from project_friction.metrics.backlog_metrics import calculate_backlog_metrics
from project_friction.metrics.ci_metrics import calculate_ci_metrics
from project_friction.metrics.pr_metrics import calculate_pr_metrics
from project_friction.workflows.builder import build_friction_workflow_definition

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestPhase4SecurityAndResearch(unittest.TestCase):

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = TestingSessionLocal()

        self.user_a = User(email="sec_usera@example.com", hashed_password=get_password_hash("passA123"), full_name="Sec User A")
        self.db.add(self.user_a)
        self.db.commit()
        self.db.refresh(self.user_a)
        self.token_a = create_access_token({"sub": str(self.user_a.id)})
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.clear()

    # --- PART A: SECURITY HARDENING & JWT/OAUTH TESTS ---

    def test_expired_jwt_rejected(self):
        """Expired JWT access token must be rejected with 401 Unauthorized."""
        expired_token = create_access_token({"sub": str(self.user_a.id)}, expires_delta=timedelta(seconds=-10))
        headers = {"Authorization": f"Bearer {expired_token}"}
        res = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertIn("expired", res.json()["detail"].lower())

    def test_invalid_jwt_signature_rejected(self):
        """JWT signed with forged secret key must be rejected with 401 Unauthorized."""
        import jwt
        forged_token = jwt.encode({"sub": str(self.user_a.id), "type": "access"}, "wrong_secret_key", algorithm=ALGORITHM)
        headers = {"Authorization": f"Bearer {forged_token}"}
        res = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(res.status_code, 401)

    def test_oauth_state_tampering_rejected(self):
        """Tampered or invalid OAuth state must be rejected during callback validation."""
        tampered_state = "invalid.tampered.oauth_state"
        res = self.client.get(f"/api/v1/auth/github/callback?code=fake_code&state={tampered_state}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("OAuth state CSRF validation failed", res.json()["detail"])

    def test_valid_oauth_state_generation_and_verification(self):
        """OAuth state generation embeds 10-minute expiry and verifies correctly."""
        state = create_oauth_state(user_id=self.user_a.id)
        payload = verify_oauth_state(state)
        self.assertEqual(payload["user_id"], self.user_a.id)
        self.assertEqual(payload["type"], "oauth_state")

    # --- PART C: WORKER CREDENTIAL SAFETY ---

    def test_worker_task_payload_does_not_contain_plaintext_github_token(self):
        """Workflow builder creates task payloads with user_id, NOT plaintext tokens."""
        wf_def = build_friction_workflow_definition(
            run_id="run-sec-1",
            owner="pallets",
            name="flask",
            time_window_days=30,
            github_token="ghp_SUPER_SECRET_PLAINTEXT_TOKEN",
            user_id=self.user_a.id,
        )

        wf_json = json.dumps(wf_def)
        self.assertNotIn("ghp_SUPER_SECRET_PLAINTEXT_TOKEN", wf_json)

        for task_spec in wf_def["tasks"]:
            payload = task_spec["payload"]
            self.assertNotIn("github_token", payload)
            self.assertEqual(payload.get("user_id"), self.user_a.id)

    # --- PART D & E: METRIC AUDIT & DATA QUALITY EDGE CASES ---

    def test_zero_activity_metrics_safety(self):
        """Zero PR, CI, and Issue activity must compute 0.0 values without NaN or division by zero."""
        pr_metrics = calculate_pr_metrics([])
        ci_metrics = calculate_ci_metrics([])
        backlog_metrics = calculate_backlog_metrics([])

        all_metrics = pr_metrics + ci_metrics + backlog_metrics
        for m in all_metrics:
            self.assertIsInstance(m["value"], float)
            self.assertEqual(m["value"], 0.0)

        dims, score, level, indicators = evaluate_friction_indicators([], [])
        self.assertEqual(level, "INSUFFICIENT_DATA")
        self.assertIsNone(score)
        self.assertEqual(indicators[0]["severity"], "INSUFFICIENT_DATA")

    def test_metric_boundary_values(self):
        """Boundary values (e.g. 100% CI failure) must clamp properly between 0 and 100."""
        ci_runs = [{"conclusion": "failure"} for _ in range(10)]
        ci_metrics = calculate_ci_metrics(ci_runs)
        self.assertEqual(ci_metrics[0]["value"], 100.0)

        dims = compute_dimension_scores(ci_metrics)
        score, level = compute_overall_friction_score(dims)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    # --- PART F & G: RESEARCH DATA VALIDATION & REPRODUCIBILITY ---

    def test_research_reproducibility(self):
        """Identical repository input data yields identical metric calculations and scores."""
        sample_prs = [
            {"created_at": "2026-09-01T10:00:00Z", "first_review_at": "2026-09-01T14:00:00Z", "merged_at": "2026-09-02T10:00:00Z", "state": "closed"},
            {"created_at": "2026-09-05T10:00:00Z", "first_review_at": "2026-09-06T10:00:00Z", "merged_at": "2026-09-07T10:00:00Z", "state": "closed"},
        ]
        sample_ci = [
            {"conclusion": "success"},
            {"conclusion": "failure"},
            {"conclusion": "success"},
            {"conclusion": "success"},
        ]

        m1 = calculate_pr_metrics(sample_prs) + calculate_ci_metrics(sample_ci)
        m2 = calculate_pr_metrics(sample_prs) + calculate_ci_metrics(sample_ci)

        dims1 = compute_dimension_scores(m1)
        dims2 = compute_dimension_scores(m2)

        score1, level1 = compute_overall_friction_score(dims1)
        score2, level2 = compute_overall_friction_score(dims2)

        self.assertEqual(dims1, dims2)
        self.assertEqual(score1, score2)
        self.assertEqual(level1, level2)


if __name__ == "__main__":
    unittest.main()
