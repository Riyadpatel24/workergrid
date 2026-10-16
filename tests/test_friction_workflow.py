import unittest
from project_friction.workflows.builder import build_friction_workflow_definition
from project_friction.tasks.registry import TASK_HANDLERS


class TestFrictionWorkflow(unittest.TestCase):
    def test_build_friction_workflow_definition(self):
        wf = build_friction_workflow_definition("run-123", "facebook", "react", 30)

        self.assertIn("facebook_react_run-123", wf["name"])
        self.assertEqual(len(wf["tasks"]), 4)

        keys = [t["key"] for t in wf["tasks"]]
        self.assertEqual(keys, ["step1_init", "step2_collect", "step3_metrics", "step4_report"])

        task_types = [t["type"] for t in wf["tasks"]]
        for tt in task_types:
            self.assertIn(tt, TASK_HANDLERS, f"Task type {tt} must be registered in TASK_HANDLERS")


if __name__ == "__main__":
    unittest.main()
