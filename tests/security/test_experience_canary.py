"""Mandatory P1 high-risk synthetic privacy/SQLite safety checks."""
import json
import sqlite3
import unittest

from my_local_ai.state.experience_migrations import (
    MESA_APP_ID, initialize_empty_experience_store, require_experience_store,
)
from my_local_ai.experience.collector import (
    collect_observation, count_owned_observations,
)

_EVENT = {
    "event_id": "event-001", "project_id": "project-001",
    "run_id": "run-001", "task_id": "task-001",
    "plan_sha256": "a"*64, "source_git_sha": "b"*40,
    "scope_ref": "scope-001", "rights_tag": "PUBLIC_SYNTHETIC",
    "outcome": "FAILED", "error_fingerprint": "c"*64,
    "environment_digest": "d"*64, "observed_at": 1795000000,
}


class ExperienceCanaryTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        initialize_empty_experience_store(self.db, explicit_new_owned_store=True)

    def tearDown(self):
        self.db.close()

    def ingest(self, values):
        return collect_observation(
            self.db, json.dumps(values), expected_project="project-001",
            expected_plan_sha="a"*64, expected_source_sha="b"*40,
            allowed_scope_refs=frozenset({"scope-001"}),
        )

    def test_append_only_and_idempotency(self):
        self.assertEqual(self.ingest(_EVENT), ("event-001", True))
        self.assertEqual(self.ingest(_EVENT), ("event-001", False))
        self.assertEqual(
            count_owned_observations(
                self.db, project_id="project-001", scope_ref="scope-001",
                source_git_sha="b"*40,
            ), 1,
        )
        for sql in (
            "UPDATE experience_events SET outcome='OBSERVED'",
            "DELETE FROM experience_events",
        ):
            with self.assertRaises(sqlite3.DatabaseError):
                self.db.execute(sql)

    def test_identical_replay_across_separate_owned_connections(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "mesa.sqlite3"
            writer = sqlite3.connect(target)
            reader = sqlite3.connect(target)
            try:
                initialize_empty_experience_store(
                    writer, explicit_new_owned_store=True)
                raw = json.dumps(_EVENT)
                params = dict(
                    expected_project="project-001", expected_plan_sha="a"*64,
                    expected_source_sha="b"*40,
                    allowed_scope_refs=frozenset({"scope-001"}),
                )
                self.assertEqual(
                    collect_observation(writer, raw, **params),
                    ("event-001", True))
                self.assertEqual(
                    collect_observation(reader, raw, **params),
                    ("event-001", False))
                with self.assertRaises(ValueError):
                    collect_observation(
                        reader, json.dumps({**_EVENT, "outcome": "HOLD"}),
                        **params)
                self.assertEqual(reader.execute(
                    "SELECT COUNT(*) FROM experience_events").fetchone()[0], 1)
            finally:
                reader.close()
                writer.close()

    def test_invalid_scoped_count_rejected(self):
        for bad in ("../bad", "PRIVATE_CANARY", "f"*39):
            with self.assertRaises(ValueError):
                count_owned_observations(
                    self.db, project_id="project-001",
                    scope_ref="scope-001", source_git_sha=bad)

    def test_reused_id_with_different_outcome_refused(self):
        self.ingest(_EVENT)
        with self.assertRaises(ValueError):
            self.ingest({**_EVENT, "outcome": "HOLD"})

    def test_secret_canary_and_spoofed_pass_refused(self):
        for key, value in (
            ("raw_prompt", "PRIVATE_CANARY"),
            ("trusted", True),
            ("independent_f18_verified", True),
            ("owner_approved", True),
            ("rights_tag", "CUSTOMER_PRIVATE"),
            ("outcome", "VERIFIED"),
            ("error_fingerprint", "PRIVATE_CANARY"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.ingest({**_EVENT, key: value})
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM experience_events"
        ).fetchone()[0], 0)

    def test_cross_source_project_scope_and_forgery_denied(self):
        for key, value in (
            ("source_git_sha", "f"*40),
            ("scope_ref", "scope-002"),
            ("project_id", "project-002"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.ingest({**_EVENT, key: value})

    def test_existing_owner_db_and_unknown_schema_refused(self):
        other = sqlite3.connect(":memory:")
        try:
            other.execute("CREATE TABLE owner_consents (secret TEXT)")
            with self.assertRaises(ValueError):
                initialize_empty_experience_store(other, explicit_new_owned_store=True)
            with self.assertRaises(ValueError):
                require_experience_store(other)
        finally:
            other.close()
        self.assertEqual(self.db.execute(
            "PRAGMA application_id"
        ).fetchone()[0], MESA_APP_ID)


if __name__ == "__main__":
    unittest.main()
