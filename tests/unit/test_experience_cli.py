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
from my_local_ai.experience.schema import ExperienceEventV1
from my_local_ai.experience.evaluation import TaskMetricsV1, persist_task_metrics
from my_local_ai.experience.curator import classify_experience, append_curation_decision
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
                "environment_digest": "d"*64, "observed_at": 1794000000,
            }
            collect_observation(
                conn, json.dumps(data), expected_project="project-001",
                expected_plan_sha="a"*64, expected_source_sha="b"*40,
                allowed_scope_refs=frozenset({"scope-001"}),
            )
            event = ExperienceEventV1(**data)
            candidate = classify_experience(
                event, strategy_digest="1"*64, proposed_action_digest="2"*64,
                expected_source_sha="b"*40, expected_scope="scope-001",
                now=1794000010, expires_at=2000000000,
            )
            append_curation_decision(
                conn, decision_id="decision-001", result=candidate,
                created_at=1794000010, expires_at=2000000000,
                expected_project="project-001", expected_source_sha="b"*40,
                expected_scope="scope-001",
            )
            baseline = TaskMetricsV1(
                "baseline-001","BASELINE","project-001",
                "a"*64,"b"*40,"e"*64,"f"*64,"scope-001",
                "PUBLIC_SYNTHETIC",120000,2,8,3,30000,None,None,None,
                task_id="TASK-001", comparison_id="experiment-001",
            )
            assisted = TaskMetricsV1(
                "assisted-001","ASSISTED","project-001",
                "a"*64,"b"*40,"e"*64,"f"*64,"scope-001",
                "PUBLIC_SYNTHETIC",60000,2,4,2,10000,None,None,None,
                task_id="TASK-001", comparison_id="experiment-001",
            )
            persist_task_metrics(conn,baseline,explicit_owned_scope=True)
            persist_task_metrics(conn,assisted,explicit_owned_scope=True)
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
        code, found = self.cli("search", "--fingerprint", "c"*64, "--environment-sha", "d"*64)
        self.assertEqual(code, 0)
        self.assertEqual(found["record_refs"], ["event-001"])
        _, inspect = self.cli("inspect", "--event-id", "event-001")
        self.assertEqual(inspect["records"][0]["outcome"], "FAILED")
        _, exported = self.cli("export-redacted")
        self.assertEqual(len(exported["records"]), 1)
        self.assertNotIn("PRIVATE_CANARY", json.dumps(exported))
        self.assertFalse(exported["execution_allowed"])

    def test_cli_persisted_comparison_is_unverified_only(self):
        code, observed = self.cli(
            "compare", "--acceptance-sha", "e"*64,
            "--environment-sha", "f"*64,
            "--task-id", "TASK-001", "--comparison-id", "experiment-001",
        )
        self.assertEqual(code, 0)
        self.assertEqual(observed["state"], "OBSERVED_UNVERIFIED")
        self.assertEqual(observed["verified_speedup"], "UNMEASURED")
        self.assertFalse(observed["execution_allowed"])
        code, mismatch = self.cli(
            "compare", "--acceptance-sha", "0"*64,
            "--environment-sha", "f"*64,
            "--task-id", "TASK-001", "--comparison-id", "experiment-001",
        )
        self.assertEqual(code, 0)
        self.assertEqual(mismatch["state"], "UNMEASURED")

    def test_recommend_cli_binds_real_plan_and_remains_inert(self):
        from my_local_ai.contracts.plan import PlanSpec

        tasks = [
            {
                "task_id": name, "req_ids": ["REQ-05"], "depends_on": [],
                "goal": "synthetic-only", "allowed_paths": [f"src/{name}.py"],
                "acceptance": ["synthetic"], "checks": [], "risk": "LOW",
                "resource_budget": {"max_calls": 1, "max_seconds": 10},
                "safety_checks": ["NO_REMOTE"], "plan_sha": None,
                "source_sha": "b"*40,
            }
            for name in ("TASK-A", "TASK-B")
        ]
        raw = json.dumps({
            "version": 1, "plan_id": "MESA-CLI-SYNTH",
            "blueprint": {
                "repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1",
                "sha": "b"*40,
            },
            "approval": {
                "status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None,
            },
            "tasks": tasks,
        })
        plan = PlanSpec.parse_json(raw)
        plan_file = Path(self.temp.name) / "synthetic.plan.json"
        plan_file.write_text(raw, encoding="utf-8")

        with sqlite3.connect(self.path) as conn:
            data = {
                "event_id": "event-002", "project_id": "project-001",
                "run_id": "run-002", "task_id": "TASK-B",
                "plan_sha256": plan.digest, "source_git_sha": "b"*40,
                "scope_ref": "scope-001", "rights_tag": "PUBLIC_SYNTHETIC",
                "outcome": "FAILED", "error_fingerprint": "c"*64,
                "environment_digest": "d"*64, "observed_at": 1794000000,
            }
            collect_observation(
                conn, json.dumps(data), expected_project="project-001",
                expected_plan_sha=plan.digest, expected_source_sha="b"*40,
                allowed_scope_refs=frozenset({"scope-001"}),
            )
            shadow = classify_experience(
                ExperienceEventV1(**data), strategy_digest="3"*64,
                proposed_action_digest="4"*64, expected_source_sha="b"*40,
                expected_scope="scope-001", now=1794000010,
                expires_at=2000000000,
            )
            append_curation_decision(
                conn, decision_id="decision-002", result=shadow,
                created_at=1794000010, expires_at=2000000000,
                expected_project="project-001", expected_source_sha="b"*40,
                expected_scope="scope-001",
            )

        args = [
            "experience", "recommend", "--db", str(self.path),
            "--project", "project-001", "--plan-sha", plan.digest,
            "--source-sha", "b"*40, "--scope", "scope-001",
            "--rights", "PUBLIC_SYNTHETIC", "--plan-file", str(plan_file),
            "--task-id", "TASK-B", "--fingerprint", "c"*64,
            "--environment-sha", "d"*64,
        ]
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = main(args)
        payload = json.loads(stream.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["state"], "SHADOW_ADVICE_ONLY")
        self.assertEqual(payload["candidate_task_ids"], ["TASK-B", "TASK-A"])
        self.assertEqual(payload["shadow_experience_refs"], ["event-002"])
        self.assertFalse(payload["execution_allowed"])
        self.assertFalse(payload["live_protected_states_read"])

        # Drift cannot select an old plan's memory or an executable path.
        args[args.index("--plan-sha") + 1] = "0"*64
        with contextlib.redirect_stdout(stream := io.StringIO()):
            status = main(args)
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(stream.getvalue())["status"], "HOLD")

        args[args.index("--plan-sha") + 1] = plan.digest
        self.path.unlink()
        with contextlib.redirect_stdout(stream := io.StringIO()):
            status = main(args)
        payload = json.loads(stream.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["candidate_task_ids"], ["TASK-A", "TASK-B"])
        self.assertEqual(payload["shadow_experience_refs"], [])
        self.assertFalse(self.path.exists())

    def test_active_wal_never_returns_stale_mesa_suggestions(self):
        # An immutable SQLite reader would ignore an uncheckpointed REVOKED
        # curation row. The safe reader must refuse the whole snapshot.
        with contextlib.closing(sqlite3.connect(self.path)) as writer:
            self.assertEqual(writer.execute(
                "PRAGMA journal_mode=WAL",
            ).fetchone()[0], "wal")
            extra = {
                "event_id": "event-003", "project_id": "project-001",
                "run_id": "run-003", "task_id": "task-001",
                "plan_sha256": "a"*64, "source_git_sha": "b"*40,
                "scope_ref": "scope-001", "rights_tag": "PUBLIC_SYNTHETIC",
                "outcome": "HOLD", "error_fingerprint": "c"*64,
                "environment_digest": "d"*64, "observed_at": 1794000011,
            }
            collect_observation(
                writer, json.dumps(extra), expected_project="project-001",
                expected_plan_sha="a"*64, expected_source_sha="b"*40,
                allowed_scope_refs=frozenset({"scope-001"}),
            )
            self.assertTrue(Path(str(self.path) + "-wal").exists())
            code, output = self.cli("search", "--fingerprint", "c"*64,
                                    "--environment-sha", "d"*64)
            self.assertEqual(code, 2)
            self.assertEqual(output["status"], "HOLD")
            self.assertFalse(output["execution_allowed"])

    def test_unknown_or_tampered_db_returns_hold(self):
        self.path.unlink()
        code, result = self.cli("status")
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(self.path.exists())

    def test_search_environment_drift_returns_baseline(self):
        code, result = self.cli(
            "search", "--fingerprint", "c"*64,
            "--environment-sha", "0"*64,
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["record_refs"], [])

    def test_search_wrong_scope_returns_no_matches(self):
        code, result = self.cli("search", "--fingerprint", "e"*64, "--environment-sha", "d"*64)
        self.assertEqual(code, 0)
        self.assertEqual(result["record_refs"], [])


if __name__ == "__main__":
    unittest.main()
