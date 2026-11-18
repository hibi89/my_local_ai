"""Local indexed MESA retrieval; no run/grant/promotion behavior."""
import json
import sqlite3
import unittest

from my_local_ai.state.experience_migrations import initialize_empty_experience_store
from my_local_ai.experience.collector import collect_observation
from my_local_ai.experience.retrieval import search_experiences

BASE = {
    "event_id": "event-001", "project_id": "project-001",
    "run_id": "run-001", "task_id": "task-001",
    "plan_sha256": "a"*64, "source_git_sha": "b"*40,
    "scope_ref": "scope-001", "rights_tag": "PUBLIC_SYNTHETIC",
    "outcome": "FAILED", "error_fingerprint": "c"*64,
    "environment_digest": "d"*64, "observed_at": 1795000000,
}


class ExperienceRetrievalTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        initialize_empty_experience_store(
            self.conn, explicit_new_owned_store=True,
        )
        for i in range(5):
            event = dict(BASE, event_id=f"event-{i:03d}", run_id=f"run-{i:03d}",
                         observed_at=1795000000+i)
            collect_observation(
                self.conn, json.dumps(event), expected_project="project-001",
                expected_plan_sha="a"*64, expected_source_sha="b"*40,
                allowed_scope_refs=frozenset({"scope-001"}),
            )

    def tearDown(self):
        self.conn.close()

    def search(self, **overrides):
        opts = dict(
            project_id="project-001", plan_sha256="a"*64,
            source_git_sha="b"*40, scope_ref="scope-001",
            rights_tag="PUBLIC_SYNTHETIC", error_fingerprint="c"*64,
            enabled=True,
        )
        opts.update(overrides)
        return search_experiences(self.conn, **opts)

    def test_exact_fingerprint_top3_and_no_authority(self):
        result = self.search()
        self.assertEqual([s.record_ids for s in result],
                         [("event-004",), ("event-003",), ("event-002",)])
        self.assertTrue(all(not s.approved and not s.execution_allowed
                            for s in result))

    def test_default_off_and_context_drift(self):
        self.assertEqual(self.search(enabled=False), ())
        for changed in (
            dict(project_id="project-999"), dict(plan_sha256="f"*64),
            dict(source_git_sha="f"*40), dict(scope_ref="scope-999"),
            dict(rights_tag="OWNED_REDACTED"),
            dict(error_fingerprint="e"*64),
        ):
            with self.subTest(changed=changed):
                self.assertEqual(self.search(**changed), ())

    def test_bad_budget_rejected(self):
        with self.assertRaises(ValueError):
            self.search(max_results=99)

    def test_unavailable_store_returns_baseline(self):
        with sqlite3.connect(":memory:") as empty:
            self.assertEqual(search_experiences(
                empty, project_id="project-001", plan_sha256="a"*64,
                source_git_sha="b"*40, scope_ref="scope-001",
                rights_tag="PUBLIC_SYNTHETIC", error_fingerprint="c"*64,
                enabled=True,
            ), ())


if __name__ == "__main__":
    unittest.main()
