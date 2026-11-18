"""P1 local CLI read-only state views and privacy safeguards."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from my_local_ai.cli import main
from my_local_ai.experience.collector import collect_observation
from my_local_ai.state.experience_migrations import initialize_empty_experience_store


class ExperienceCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "synthetic.mesa.sqlite3"
        conn = sqlite3.connect(self.path)
        try:
            initialize_empty_experience_store(conn, explicit_new_owned_store=True)
            data = {
                "event_id": "event-001", "project_id": "project-001",
                "run_id": "run-001", "task_id": "task-001",
                "plan_sha256": "a"*64, "source_git_sha": "b"*40,
                "scope_ref": "scope-001", "rights_tag": "PUBLIC_SYNTHETIC",
                "outcome": "FAILED", "error_fingerprint": "c"*64,
                "environment_digest": "d"*64, "observed_at": 1795000000,
            }
            collect_observation(
                conn, json.dumps(data), expected_project="project-001",
                expected_plan_sha="a"*64, expected_source_sha="b"*40,
                allowed_scope_refs=frozenset({"scope-001"}),
            )
        finally:
            conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, action, *extra):
        args = [
            "experience", action, "--db", str(self.path),
            "--project", "project-001", "--plan-sha", "a"*64,
            "--source-sha", "b"*40, "--scope", "scope-001",
            "--rights", "PUBLIC_SYNTHETIC",
            *extra,
        ]
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(args)
        return code, json.loads(stream.getvalue())

    def test_cli_status_search_inspect_and_export(self):
        status, result = self.cli("status")
        self.assertEqual(status, 0)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["redacted_count_capped"], 1)
        code, found = self.cli("search", "--fingerprint", "c"*64)
        self.assertEqual(code, 0)
        self.assertEqual(found["record_refs"], ["event-001"])
        _, inspect = self.cli("inspect", "--event-id", "event-001")
        self.assertEqual(inspect["records"][0]["outcome"], "FAILED")
        _, exported = self.cli("export-redacted")
        self.assertEqual(len(exported["records"]), 1)
        self.assertNotIn("PRIVATE_CANARY", json.dumps(exported))
        self.assertFalse(exported["execution_allowed"])

    def test_unknown_or_tampered_db_returns_hold(self):
        self.path.unlink()
        code, result = self.cli("status")
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(self.path.exists())

    def test_search_wrong_scope_returns_no_matches(self):
        code, result = self.cli("search", "--fingerprint", "e"*64)
        self.assertEqual(code, 0)
        self.assertEqual(result["record_refs"], [])


if __name__ == "__main__":
    unittest.main()
