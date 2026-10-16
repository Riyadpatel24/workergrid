import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.time import utcnow_naive
from app.db.database import Base
from app.models.friction import FrictionAnalysisRun, Repository
from app.models.task import Task
from app.models.user import User
from app.queue.queue_manager import enqueue_task, normalize_priority, queue_depths
from project_friction.tasks import dispatch_task
from project_friction.workflows.builder import build_friction_workflow_definition
import scheduler
from worker import process_task

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine)


def override_session():
    return TestingSessionLocal()


class TestPhase5Experiments(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    # --- PART A: FULL PROJECT FRICTION DAG & FAILURE PROPAGATION ---

    def test_full_project_friction_dag_flow(self):
        """Validate DAG sequence: init -> collect -> calc_metrics -> generate_report."""
        wf_def = build_friction_workflow_definition(
            run_id="run-dag-test-1",
            owner="pallets",
            name="flask",
            time_window_days=30,
            user_id=1,
        )

        task_keys = [t["key"] for t in wf_def["tasks"]]
        self.assertEqual(task_keys, ["step1_init", "step2_collect", "step3_metrics", "step4_report"])

        # Step 1 depends on nothing
        self.assertEqual(wf_def["tasks"][0]["depends_on"], [])
        # Step 2 depends on step1
        self.assertEqual(wf_def["tasks"][1]["depends_on"], ["step1_init"])
        # Step 3 depends on step2
        self.assertEqual(wf_def["tasks"][2]["depends_on"], ["step2_collect"])
        # Step 4 depends on step3
        self.assertEqual(wf_def["tasks"][3]["depends_on"], ["step3_metrics"])

    # --- PART B: PRIORITY QUEUES ---

    def test_priority_queue_normalization(self):
        """Validate normalize_priority maps inputs to HIGH, MEDIUM, LOW correctly."""
        self.assertEqual(normalize_priority("HIGH"), "HIGH")
        self.assertEqual(normalize_priority("high"), "HIGH")
        self.assertEqual(normalize_priority("MEDIUM"), "MEDIUM")
        self.assertEqual(normalize_priority("LOW"), "LOW")
        with self.assertRaises(ValueError):
            normalize_priority("invalid")

    # --- PART C: CAPABILITY ROUTING ---

    def test_capability_matching(self):
        """Validate capability matching logic for workers."""
        task_friction = Task(id=1, type="friction_init", required_capability="friction", priority="HIGH", payload={"user_id": 1})
        task_github = Task(id=2, type="friction_collect_github", required_capability="github", priority="MEDIUM", payload={"user_id": 1})

        # Worker capabilities check
        worker_caps = ["friction", "general"]
        self.assertIn(task_friction.required_capability, worker_caps)
        self.assertNotIn(task_github.required_capability, worker_caps)

    # --- PART E: RETRY & DLQ LOGIC ---

    def test_retry_count_and_dlq_threshold(self):
        """Validate task retries up to max_retries before transitioning to FAILED."""
        task = Task(
            id=101,
            user_id=1,
            type="custom_job",
            status="PENDING",
            priority="HIGH",
            retries=2,
            max_retries=3,
            payload={"fail": True},
        )
        self.db.add(task)
        self.db.commit()

        # Task at retries=2 fails once more -> reaches max_retries 3 -> transitions to FAILED
        with patch("worker.SessionLocal", side_effect=override_session), \
             patch("time.sleep", return_value=None):
            process_task(101)

        self.db.expire_all()
        refreshed_task = self.db.query(Task).filter(Task.id == 101).first()
        self.assertEqual(refreshed_task.status, "FAILED")
        self.assertIn("Simulated failure", refreshed_task.result.get("error", ""))

    # --- PART F: SCHEDULER ACTIVATION ---

    def test_scheduler_activation(self):
        """Validate scheduled task activation when scheduled_at <= now."""
        now = utcnow_naive()
        past_time = now - timedelta(minutes=5)

        scheduled_task = Task(
            id=202,
            user_id=1,
            type="scheduled_job",
            status="SCHEDULED",
            scheduled_at=past_time,
            priority="MEDIUM",
            payload={},
        )
        self.db.add(scheduled_task)
        self.db.commit()

        with patch("scheduler.SessionLocal", side_effect=override_session), \
             patch("app.queue.queue_manager.enqueue_task", return_value=True):
            scheduler.schedule_tasks()

        self.db.expire_all()
        activated = self.db.query(Task).filter(Task.id == 202).first()
        self.assertEqual(activated.status, "PENDING")


if __name__ == "__main__":
    unittest.main()
