"""Synthetic high-risk curation state persistence and v1 rejection."""
import sqlite3
import unittest
from my_local_ai.state.experience_migrations import (
    MESA_APP_ID, initialize_empty_experience_store, require_experience_store,
)
from my_local_ai.experience.collector import collect_observation
from my_local_ai.experience.curator import (
    append_curation_decision, classify_experience,
)
from my_local_ai.experience.schema import ExperienceEventV1
import json

EVENT = ExperienceEventV1(
    "event-001","project-001","run-001","task-001",
    "a"*64,"b"*40,"scope-001","PUBLIC_SYNTHETIC","FAILED",
    "c"*64,"d"*64,1795000000,
)


class CurationStorageTest(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(":memory:")
        initialize_empty_experience_store(self.conn, explicit_new_owned_store=True)
        collect_observation(
            self.conn, json.dumps({k:v for k,v in EVENT.to_redacted_dict().items()
                                   if k not in {"evidence_stage","owner_approved",
                                                "execution_allowed","independent_f18_verified"}}),
            expected_project=EVENT.project_id, expected_plan_sha=EVENT.plan_sha256,
            expected_source_sha=EVENT.source_git_sha,
            allowed_scope_refs=frozenset({EVENT.scope_ref}),
        )

    def tearDown(self):
        self.conn.close()

    def write(self, decision_id="decision-001", **changes):
        state=classify_experience(
            EVENT, strategy_digest="1"*64, proposed_action_digest="2"*64,
            expected_source_sha="b"*40, expected_scope="scope-001",
            now=1795000010, expires_at=2000000000,
        )
        args=dict(
            conn=self.conn, decision_id=decision_id, result=state,
            created_at=1795000010, expires_at=2000000000,
            expected_project="project-001", expected_source_sha="b"*40,
            expected_scope="scope-001", conflict_digest="3"*64,
        )
        args.update(changes)
        return append_curation_decision(**args)

    def test_append_only_idempotent(self):
        self.assertTrue(self.write())
        self.assertFalse(self.write())
        for q in (
            "DELETE FROM experience_curation_events",
            "UPDATE experience_curation_events SET state='REVOKED'",
        ):
            with self.assertRaises(sqlite3.DatabaseError):
                self.conn.execute(q)
        self.assertEqual(require_experience_store(self.conn,require_v2=True),2)

    def test_changed_replay_cross_scope_and_backdate_blocked(self):
        self.write()
        with self.assertRaises(ValueError):
            self.write(expires_at=2000000001)
        with self.assertRaises(ValueError):
            self.write("decision-002", expected_project="other-project")
        with self.assertRaises(ValueError):
            self.write("decision-002", created_at=1795000009)

    def test_prior_non_mesa_db_not_upgraded(self):
        foreign=sqlite3.connect(":memory:")
        try:
            foreign.execute("CREATE TABLE owner_consents(a TEXT)")
            with self.assertRaises(ValueError):
                initialize_empty_experience_store(
                    foreign, explicit_new_owned_store=True)
            self.assertEqual(foreign.execute("PRAGMA application_id").fetchone()[0],0)
            with self.assertRaises(ValueError):
                require_experience_store(foreign,require_v2=True)
        finally:
            foreign.close()

if __name__=="__main__":
    unittest.main()
