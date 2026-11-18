"""Synthetic Controller + MESA OFF/ON path, no task execution."""
import json
import sqlite3
import unittest

from my_local_ai.contracts.plan import PlanSpec
from my_local_ai.controller.experience_selector import select_with_experience
from my_local_ai.experience.collector import collect_observation
from my_local_ai.state.experience_migrations import initialize_empty_experience_store

SOURCE = "a"*40
ERR = "c"*64


def _plan():
    tasks = [
        {"task_id": name, "req_ids": ["REQ-05"], "depends_on": depends,
         "goal": "synthetic local", "allowed_paths": [f"src/{name}.py"],
         "acceptance": ["synthetic"], "checks": [], "risk": risk,
         "resource_budget": {"max_calls": 1, "max_seconds": 10},
         "safety_checks": ["NO_REMOTE"], "plan_sha": None, "source_sha": SOURCE}
        for name, risk, depends in [
            ("TASK-A", "LOW", []), ("TASK-B", "LOW", []),
            ("TASK-C", "HIGH", []), ("TASK-D", "LOW", ["TASK-C"]),
        ]
    ]
    return json.dumps({
        "version": 1, "plan_id": "MESA-SYNTH-001",
        "blueprint": {
            "repo": "hibi89/my_local_ai",
            "branch": "dev/instant-implementation-v1", "sha": SOURCE,
        },
        "approval": {
            "status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None,
        },
        "tasks": tasks,
    })


class ExperienceControllerOfflineTest(unittest.TestCase):
    def setUp(self):
        self.raw = _plan()
        self.plan = PlanSpec.parse_json(self.raw)
        self.states = {k: "READY" for k in ("TASK-A", "TASK-B", "TASK-C", "TASK-D")}
        self.conn = sqlite3.connect(":memory:")
        initialize_empty_experience_store(self.conn, explicit_new_owned_store=True)
        record = {
            "event_id": "event-001", "project_id": "project-001",
            "run_id": "run-001", "task_id": "TASK-B",
            "plan_sha256": self.plan.digest, "source_git_sha": SOURCE,
            "scope_ref": "scope-001", "rights_tag": "PUBLIC_SYNTHETIC",
            "outcome": "FAILED", "error_fingerprint": ERR,
            "environment_digest": "d"*64, "observed_at": 1795000000,
        }
        collect_observation(
            self.conn, json.dumps(record), expected_project="project-001",
            expected_plan_sha=self.plan.digest, expected_source_sha=SOURCE,
            allowed_scope_refs=frozenset({"scope-001"}),
        )

    def tearDown(self):
        self.conn.close()

    def select(self, **changes):
        data = dict(
            plan_json=self.raw, protected_states=self.states,
            experience_conn=self.conn, enabled=True,
            project_id="project-001", scope_ref="scope-001",
            rights_tag="PUBLIC_SYNTHETIC",
            task_error_fingerprints={"TASK-B": ERR},
        )
        data.update(changes)
        return select_with_experience(**data)

    def test_controller_tie_order_is_only_advisory(self):
        result = self.select()
        self.assertEqual(result.status, "SHADOW_ADVICE_ONLY")
        self.assertEqual(result.candidate_task_ids,
                         ("TASK-B", "TASK-A", "TASK-C"))
        self.assertEqual(result.experience_refs, ("event-001",))
        self.assertFalse(result.execution_allowed)
        self.assertFalse(result.owner_go)
        self.assertNotIn("TASK-D", result.candidate_task_ids)

    def test_missing_memory_does_not_break_qwen_baseline(self):
        for change in (
            dict(enabled=False), dict(experience_conn=None),
            dict(scope_ref="scope-999"),
            dict(task_error_fingerprints={"TASK-B": "e"*64}),
        ):
            with self.subTest(change=change):
                result = self.select(**change)
                self.assertEqual(result.candidate_task_ids,
                                 ("TASK-A", "TASK-B", "TASK-C"))
                self.assertEqual(result.experience_refs, ())

    def test_lease_and_stale_sha_keep_original_gate(self):
        proposal = self.select(active_leases=("TASK-B",))
        self.assertEqual(proposal.candidate_task_ids, ("TASK-A", "TASK-C"))
        self.assertNotIn("TASK-B", proposal.candidate_task_ids)

    def test_untrusted_context_does_not_launch_anything(self):
        with self.assertRaises(ValueError):
            self.select(task_error_fingerprints={str(i): ERR for i in range(300)})


if __name__ == "__main__":
    unittest.main()
