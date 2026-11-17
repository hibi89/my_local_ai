"""Synthetic deterministic queue policy; no agent or Git worktrees started."""
import dataclasses
import unittest

from my_local_ai.ax_runtime.queue import QueuePolicy
from my_local_ai.contracts.task import TaskSpec

SHA = "a" * 40
PLAN = "b" * 64

def task(name, deps=()):
    return TaskSpec.parse({
        "task_id": name,
        "req_ids": ["REQ-08"],
        "depends_on": list(deps),
        "goal": "Synthetic scheduling",
        "allowed_paths": ["src/synthetic.py"],
        "acceptance": ["synthetic-only"],
        "checks": [],
        "risk": "LOW",
        "resource_budget": {"max_calls": 1, "max_seconds": 10},
        "safety_checks": ["NO_REMOTE"],
        "plan_sha": PLAN,
        "source_sha": SHA,
    })

class QueueTests(unittest.TestCase):
    def test_independent_ready_survives_hold(self):
        planner = QueuePolicy((task("TASK-001"), task("TASK-002", ("TASK-001",)), task("TASK-003")), PLAN)
        states = {"TASK-001": "HOLD", "TASK-002": "READY", "TASK-003": "READY"}
        result = planner.propose_ready(states)
        self.assertEqual([r.task_id for r in result], ["TASK-003"])
        self.assertFalse(result[0].runnable)

    def test_dependency_label_cannot_self_certify(self):
        planner = QueuePolicy((task("TASK-001"), task("TASK-002", ("TASK-001",))), PLAN)
        states = {"TASK-001": "VERIFIED", "TASK-002": "READY"}
        self.assertEqual(planner.propose_ready(states), ())
        self.assertEqual([r.task_id for r in planner.propose_ready(states, independently_verified={"TASK-001"})], ["TASK-002"])

    def test_active_lease_suppresses_duplicate_candidate(self):
        planner = QueuePolicy((task("TASK-001"),), PLAN)
        states = {"TASK-001": "READY"}
        self.assertEqual(planner.propose_ready(states, active_leases={"TASK-001"}), ())

    def test_unknown_dependency_rejected(self):
        with self.assertRaises(ValueError):
            QueuePolicy((task("TASK-001", ("MISSING",)),), PLAN)

    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            QueuePolicy((task("TASK-001", ("TASK-002",)), task("TASK-002", ("TASK-001",))), PLAN)

    def test_unknown_status_and_missing_status_rejected(self):
        planner = QueuePolicy((task("TASK-001"),), PLAN)
        with self.assertRaises(ValueError):
            planner.propose_ready({"TASK-001": "RUNNING"})
        with self.assertRaises(ValueError):
            planner.propose_ready({})

    def test_unknown_trusted_id_rejected(self):
        planner = QueuePolicy((task("TASK-001"),), PLAN)
        with self.assertRaises(ValueError):
            planner.propose_ready({"TASK-001": "READY"}, independently_verified={"OTHER"})

    def test_key_pinned_to_plan_task_baseline(self):
        first = QueuePolicy.idempotency_key(PLAN, "TASK-001", SHA)
        self.assertEqual(first, QueuePolicy.idempotency_key(PLAN, "TASK-001", SHA))
        self.assertNotEqual(first, QueuePolicy.idempotency_key(PLAN, "TASK-002", SHA))
        with self.assertRaises(ValueError):
            QueuePolicy.idempotency_key(PLAN, "TASK-001", "not-a-sha")

if __name__ == "__main__":
    unittest.main()
