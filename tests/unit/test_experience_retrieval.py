"""MESA curation, expiry, revocation, conflict and exact-SHA retrieval."""
import json
import sqlite3
import unittest

from my_local_ai.state.experience_migrations import initialize_empty_experience_store
from my_local_ai.experience.collector import collect_observation
from my_local_ai.experience.retrieval import search_experiences
from my_local_ai.experience.curator import classify_experience, append_curation_decision
from my_local_ai.experience.schema import ExperienceEventV1

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
        self.conn=sqlite3.connect(":memory:")
        initialize_empty_experience_store(self.conn, explicit_new_owned_store=True)
        self.events=[]
        for i in range(5):
            raw=dict(BASE, event_id=f"event-{i:03d}", run_id=f"run-{i:03d}",
                     observed_at=1795000000+i)
            collect_observation(
                self.conn, json.dumps(raw), expected_project="project-001",
                expected_plan_sha="a"*64, expected_source_sha="b"*40,
                allowed_scope_refs=frozenset({"scope-001"}),
            )
            event=ExperienceEventV1(**raw)
            self.events.append(event)
            self.mark(event, f"decision-{i:03d}", "1"*64)

    def tearDown(self):
        self.conn.close()

    def mark(self, event, id, strategy, *, now=1795000020,
             expires=2000000000, revoked=False, conflict=None):
        result=classify_experience(
            event, strategy_digest=strategy, proposed_action_digest="2"*64,
            expected_source_sha="b"*40, expected_scope="scope-001",
            now=now, expires_at=expires,
            revoked_event_ids=frozenset({event.event_id}) if revoked else frozenset(),
        )
        return append_curation_decision(
            self.conn,decision_id=id,result=result,created_at=now,
            expires_at=expires,expected_project="project-001",
            expected_source_sha="b"*40,expected_scope="scope-001",
            conflict_digest=conflict,
        )

    def search(self, **overrides):
        opts=dict(project_id="project-001",plan_sha256="a"*64,
                  source_git_sha="b"*40,scope_ref="scope-001",
                  rights_tag="PUBLIC_SYNTHETIC",error_fingerprint="c"*64,
                  enabled=True,now_seconds=1795000030,
                  environment_digest="d"*64)
        opts.update(overrides)
        return search_experiences(self.conn,**opts)

    def test_curated_top3_non_authoritative(self):
        result=self.search()
        self.assertEqual([s.record_ids for s in result],
                         [("event-004",),("event-003",),("event-002",)])
        self.assertTrue(all(not s.approved and not s.execution_allowed
                            for s in result))

    def test_default_off_scope_drift_and_bad_budget(self):
        self.assertEqual(self.search(enabled=False),())
        for delta in (
            dict(project_id="project-999"),dict(plan_sha256="f"*64),
            dict(source_git_sha="f"*40),dict(scope_ref="scope-999"),
            dict(rights_tag="OWNED_REDACTED"),
            dict(error_fingerprint="e"*64),
            dict(environment_digest="e"*64),
            dict(environment_digest=None),
        ):
            with self.subTest(delta=delta):
                self.assertEqual(self.search(**delta),())
        with self.assertRaises(ValueError):
            self.search(max_results=4)

    def test_revocation_and_expiry_exclude_previous_hit(self):
        self.mark(self.events[4],"decision-revoke-004","1"*64,
                  now=1795000025,revoked=True)
        self.assertEqual([s.record_ids for s in self.search()],
                         [("event-003",),("event-002",),("event-001",)])
        self.assertEqual(self.search(now_seconds=2000000000),())

    def test_conflicting_strategy_group_excluded(self):
        for i,strategy in ((3,"1"*64),(4,"4"*64)):
            self.mark(self.events[i],f"decision-conflict-{i:03d}",strategy,
                      now=1795000025,conflict="f"*64)
        ids=[s.record_ids for s in self.search()]
        self.assertNotIn(("event-004",),ids)
        self.assertNotIn(("event-003",),ids)

    def test_unavailable_database_is_empty_memory(self):
        with sqlite3.connect(":memory:") as empty:
            self.assertEqual(search_experiences(
                empty,project_id="project-001",plan_sha256="a"*64,
                source_git_sha="b"*40,scope_ref="scope-001",
                rights_tag="PUBLIC_SYNTHETIC",error_fingerprint="c"*64,
                enabled=True,now_seconds=1795000030,
                environment_digest="d"*64),())


if __name__ == "__main__":
    unittest.main()
