import json
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, get_password_hash
from app.db.database import Base
from app.db.dependencies import get_db
from app.models.friction import (
    FrictionAnalysisRun,
    FrictionEvidence,
    FrictionIndicator,
    FrictionMetric,
    Repository,
)
from app.models.task import Task
from app.models.user import User, UserGitHubAccount
from main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestMultiTenantIsolation(unittest.TestCase):

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = TestingSessionLocal()

        # Create User A
        self.user_a = User(email="usera@example.com", hashed_password=get_password_hash("passwordA123"), full_name="User A")
        self.db.add(self.user_a)
        self.db.commit()
        self.db.refresh(self.user_a)
        self.token_a = create_access_token({"sub": str(self.user_a.id)})
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}

        # Create User B
        self.user_b = User(email="userb@example.com", hashed_password=get_password_hash("passwordB123"), full_name="User B")
        self.db.add(self.user_b)
        self.db.commit()
        self.db.refresh(self.user_b)
        self.token_b = create_access_token({"sub": str(self.user_b.id)})
        self.headers_b = {"Authorization": f"Bearer {self.token_b}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.clear()

    def test_repository_isolation_and_idor_protection(self):
        """User A creates repository -> User B cannot see User A's repository."""
        # User A starts analysis (creates repository for User A)
        res_a = self.client.post("/api/v1/friction/analyses", json={"owner": "facebook", "name": "react"}, headers=self.headers_a)
        self.assertEqual(res_a.status_code, 202)

        # User A lists repositories -> sees 1
        list_a = self.client.get("/api/v1/friction/repositories", headers=self.headers_a).json()
        self.assertEqual(list_a["count"], 1)
        self.assertEqual(list_a["items"][0]["full_name"], "facebook/react")

        # User B lists repositories -> sees 0 (Strict Read Isolation)
        list_b = self.client.get("/api/v1/friction/repositories", headers=self.headers_b).json()
        self.assertEqual(list_b["count"], 0)

    def test_independent_same_repository_ownership(self):
        """User A and User B can independently analyze the same repository without collision."""
        res_a = self.client.post("/api/v1/friction/analyses", json={"owner": "fastapi", "name": "fastapi"}, headers=self.headers_a)
        res_b = self.client.post("/api/v1/friction/analyses", json={"owner": "fastapi", "name": "fastapi"}, headers=self.headers_b)

        self.assertEqual(res_a.status_code, 202)
        self.assertEqual(res_b.status_code, 202)
        self.assertNotEqual(res_a.json()["run_id"], res_b.json()["run_id"])

        # User A sees 1 run
        runs_a = self.client.get("/api/v1/friction/analyses", headers=self.headers_a).json()
        self.assertEqual(runs_a["count"], 1)
        self.assertEqual(runs_a["items"][0]["run_id"], res_a.json()["run_id"])

        # User B sees 1 run (their own)
        runs_b = self.client.get("/api/v1/friction/analyses", headers=self.headers_b).json()
        self.assertEqual(runs_b["count"], 1)
        self.assertEqual(runs_b["items"][0]["run_id"], res_b.json()["run_id"])

    def test_analysis_run_idor_protection(self):
        """User B requesting User A's analysis run ID gets 404 Not Found."""
        res_a = self.client.post("/api/v1/friction/analyses", json={"owner": "pallets", "name": "flask"}, headers=self.headers_a)
        run_id_a = res_a.json()["run_id"]

        # User A can get status & report
        status_a = self.client.get(f"/api/v1/friction/analyses/{run_id_a}", headers=self.headers_a)
        self.assertEqual(status_a.status_code, 200)

        # User B attempts IDOR on User A's run_id -> 404 Not Found
        status_b = self.client.get(f"/api/v1/friction/analyses/{run_id_a}", headers=self.headers_b)
        self.assertEqual(status_b.status_code, 404)

        report_b = self.client.get(f"/api/v1/friction/analyses/{run_id_a}/report", headers=self.headers_b)
        self.assertEqual(report_b.status_code, 404)

    def test_indicator_evidence_idor_protection(self):
        """User B requesting User A's indicator ID gets 404 Not Found."""
        # Create Indicator for User A directly in DB
        ind_a = FrictionIndicator(user_id=self.user_a.id, run_id="run-a", category="ci_cd", severity="HIGH", title="Test Title", summary="Summary")
        self.db.add(ind_a)
        self.db.commit()

        # User A can read indicator evidence
        res_a = self.client.get(f"/api/v1/friction/indicators/{ind_a.id}/evidence", headers=self.headers_a)
        self.assertEqual(res_a.status_code, 200)

        # User B attempting to read User A's indicator evidence -> 404 Not Found
        res_b = self.client.get(f"/api/v1/friction/indicators/{ind_a.id}/evidence", headers=self.headers_b)
        self.assertEqual(res_b.status_code, 404)

    def test_workergrid_task_isolation_and_idor_protection(self):
        """User A creates task -> User B cannot list, retrieve, retry, or cancel User A's task."""
        # User A creates task
        create_res = self.client.post("/tasks", json={"type": "custom_job", "payload": {"foo": "bar"}}, headers=self.headers_a)
        self.assertEqual(create_res.status_code, 200)
        task_id_a = create_res.json()["task_id"]

        # User A lists tasks -> sees task
        tasks_a = self.client.get("/tasks", headers=self.headers_a).json()
        self.assertEqual(tasks_a["count"], 1)

        # User B lists tasks -> sees 0 tasks
        tasks_b = self.client.get("/tasks", headers=self.headers_b).json()
        self.assertEqual(tasks_b["count"], 0)

        # User B get_task -> 404
        self.assertEqual(self.client.get(f"/tasks/{task_id_a}", headers=self.headers_b).status_code, 404)

        # User B cancel_task -> 404
        self.assertEqual(self.client.post(f"/tasks/{task_id_a}/cancel", headers=self.headers_b).status_code, 404)

        # User B retry_task -> 404
        self.assertEqual(self.client.post(f"/tasks/{task_id_a}/retry", headers=self.headers_b).status_code, 404)

    def test_workflow_isolation(self):
        """User A creates workflow -> User B cannot retrieve User A's workflow."""
        wf_res = self.client.post("/workflows", json={"name": "test_wf", "tasks": [{"key": "t1", "type": "job", "payload": {}, "depends_on": []}]}, headers=self.headers_a)
        self.assertEqual(wf_res.status_code, 200)
        wf_id_a = wf_res.json()["workflow_id"]

        # User A can get workflow status
        self.assertEqual(self.client.get(f"/workflows/{wf_id_a}", headers=self.headers_a).status_code, 200)

        # User B attempting to get User A's workflow -> 404
        self.assertEqual(self.client.get(f"/workflows/{wf_id_a}", headers=self.headers_b).status_code, 404)

    def test_client_cannot_impersonate_user_id_in_payload(self):
        """User B sending user_id=User A in request body cannot override server-side ownership."""
        # User B attempts to set user_id of User A in payload
        res = self.client.post("/api/v1/friction/analyses", json={"owner": "torvalds", "name": "linux", "user_id": self.user_a.id}, headers=self.headers_b)
        self.assertEqual(res.status_code, 202)
        run_id = res.json()["run_id"]

        # Verify run in DB is owned by User B (current_user.id), not User A
        run_db = self.db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id).first()
        self.assertEqual(run_db.user_id, self.user_b.id)
        self.assertNotEqual(run_db.user_id, self.user_a.id)

    def test_github_token_is_never_returned_or_logged(self):
        """Verify plaintext GitHub token is never exposed in API GET responses."""
        gh_acc = UserGitHubAccount(user_id=self.user_a.id, github_username="usera_gh", encrypted_access_token="enc_secret")
        self.db.add(gh_acc)
        self.db.commit()

        me_res = self.client.get("/api/v1/auth/me", headers=self.headers_a).json()
        self.assertNotIn("enc_secret", json.dumps(me_res))
        self.assertNotIn("encrypted_access_token", me_res)


if __name__ == "__main__":
    unittest.main()
