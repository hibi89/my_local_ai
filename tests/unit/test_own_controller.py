"""Controller pure synthetic unit tests; no original EAI import or task launch."""
import json
import unittest

from my_local_ai.controller.decision import Controller
from my_local_ai.contracts.plan import PlanSpec

BASE = "a" * 40


def plan():
    def task(task_id, risk, depends_on=()):
        return {
            "task_id": task_id, "req_ids": ["REQ-05"],
            "depends_on": list(depends_on), "goal": "synthetic-local-controller",
            "allowed_paths": [f"src/{task_id}.py"],
            "acceptance": ["synthetic contract"], "checks": [],
            "risk": risk, "resource_budget": {"max_calls": 1, "max_seconds": 10},
            "safety_checks": ["NO_REMOTE"], "plan_sha": None, "source_sha": BASE,
        }
    value = {
        "version": 1, "plan_id": "CONTROLLER-SYNTH-001",
        "blueprint": {"repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1", "sha": BASE},
        "approval": {"status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None},
        "tasks": [task("TASK-A", "HIGH"),
                  task("TASK-B", "LOW"),
                  task("TASK-C", "LOW"),
                  task("TASK-D", "LOW", ("TASK-A",))],
    }
    return PlanSpec.parse_json(json.dumps(value))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller(plan())
        self.states = {name: "READY" for name in ("TASK-A", "TASK-B", "TASK-C", "TASK-D")}

    def test_base_controller_independent_of_eai(self):
        result = self.controller.propose(self.states)
        self.assertEqual([d.task_id for d in result.decisions], ["TASK-B", "TASK-C", "TASK-A"])
        self.assertEqual(result.advisory_status, "DISABLED")
        self.assertFalse(result.execution_allowed)
        self.assertTrue(all(not d.runnable for d in result.decisions))

    def test_advisor_cannot_override_immutable_risk_order(self):
        hint = json.dumps({"version": 1, "hints": [
            {"task_id": "TASK-C", "rank": 0}, {"task_id": "TASK-B", "rank": 3},
            {"task_id": "TASK-A", "rank": 0},
        ]})
        result = self.controller.propose(self.states, advisory_json=hint)
        self.assertEqual([d.task_id for d in result.decisions], ["TASK-C", "TASK-B", "TASK-A"])
        self.assertFalse(result.owner_go)
        self.assertFalse(result.verified)

    def test_injected_permission_in_advisor_is_ignored(self):
        for hint in (
            '{"version":1,"hints":[],"owner_go":true}',
            '{"version":1,"hints":[{"task_id":"TASK-B","rank":0,"allowed_paths":[".env"]}]}',
            '{"version":1,"hints":[{"task_id":"TASK-D","rank":0}]}',
            '{"version":1,"hints":[{"task_id":"TASK-B","rank":0}],"version":1}',
            '{"version":1,"hints":[{"task_id":"TASK-B","rank":true}]}',
        ):
            with self.subTest(hint=hint):
                result = self.controller.propose(self.states, advisory_json=hint)
                self.assertEqual(result.advisory_status, "INVALID_HINTS_IGNORED")
                self.assertEqual([d.task_id for d in result.decisions], ["TASK-B", "TASK-C", "TASK-A"])

    def test_guest_verified_label_does_not_unlock_dependencies(self):
        self.states["TASK-A"] = "VERIFIED"
        result = self.controller.propose(self.states)
        self.assertNotIn("TASK-D", [d.task_id for d in result.decisions])
        protected = self.controller.propose(self.states, independently_verified={"TASK-A"})
        self.assertIn("TASK-D", [d.task_id for d in protected.decisions])
        self.assertTrue(all(not d.runnable for d in protected.decisions))

    def test_active_lease_prevents_duplicate_candidate(self):
        result = self.controller.propose(self.states, active_leases={"TASK-B"})
        self.assertEqual([d.task_id for d in result.decisions], ["TASK-C", "TASK-A"])

    def test_wrong_states_fail_closed(self):
        with self.assertRaises(ValueError):
            self.controller.propose({})
        self.states["TASK-A"] = "SELF_VERIFIED"
        with self.assertRaises(ValueError):
            self.controller.propose(self.states)

    def test_plan_claim_not_authoritative(self):
        p = plan()
        self.assertFalse(p.approved)
        result = self.controller.propose({t.task_id: "READY" for t in p.tasks})
        self.assertFalse(result.owner_go)
        self.assertFalse(result.execution_allowed)


if __name__ == "__main__":
    unittest.main()
