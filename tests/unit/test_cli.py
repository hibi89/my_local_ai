"""P1 synthetic CLI tests; must have zero side effects."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import shutil
from unittest.mock import patch

from my_local_ai.cli import main

SHA = "a" * 40

def minimal_plan():
    return {
        "version": 1,
        "plan_id": "TEST-001",
        "blueprint": {"repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1", "sha": SHA},
        "approval": {"status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None},
        "tasks": [{
            "task_id": "TEST-001", "req_ids": ["REQ-04"], "depends_on": [],
            "goal": "No execution", "allowed_paths": ["src/demo.py"],
            "acceptance": ["synthetic success"], "checks": [],
            "risk": "LOW", "resource_budget": {"max_calls": 1, "max_seconds": 20},
            "safety_checks": ["NO_REMOTE"], "plan_sha": None, "source_sha": SHA,
        }],
    }

def invoke(*argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(list(argv))
    return code, json.loads(buffer.getvalue())

class CliTests(unittest.TestCase):
    def test_doctor_is_read_only(self):
        code, result = invoke("doctor")
        self.assertEqual(code, 0)
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(result["p2"], "LOCKED")
        self.assertEqual(result["actual_ollama_probe"], "NOT_RUN")

    def test_status_is_redacted_and_not_verified(self):
        code, result = invoke("status")
        self.assertEqual(code, 0)
        self.assertEqual(result["program"], "my_local_ai")
        self.assertEqual(result["verified_rate"], "UNASSESSED")
        self.assertFalse(result["execution_allowed"])

    def test_queue_status_has_no_execution(self):
        code, result = invoke("queue", "status")
        self.assertEqual(code, 0)
        self.assertEqual(result["tasks_total"], 28)
        self.assertFalse(result["execution_allowed"])

    def test_valid_plan_schema_does_not_grant_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            data = json.dumps(minimal_plan())
            path.write_text(data, encoding="utf-8")
            code, result = invoke("plan", "validate", "--file", str(path))
            self.assertEqual(code, 0)
            self.assertTrue(result["valid_schema"])
            self.assertFalse(result["owner_approval_verified"])
            self.assertFalse(result["execution_allowed"])
            self.assertEqual(path.read_text(encoding="utf-8"), data)

    def test_invalid_plan_holds_without_leaking_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private.json"
            path.write_text('{"password":"DO_NOT_ECHO"}', encoding="utf-8")
            code, result = invoke("plan", "validate", "--file", str(path))
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "HOLD")
            self.assertNotIn("DO_NOT_ECHO", json.dumps(result))

    def test_nonexistent_plan_holds(self):
        code, result = invoke("plan", "validate", "--file", "no-such-synthetic-plan.json")
        self.assertEqual(code, 2)
        self.assertFalse(result["execution_allowed"])

class CliNextAndControlTests(unittest.TestCase):
    def test_code_ready_is_visible_but_not_execution_ready(self):
        code,result=invoke("queue","next")
        self.assertEqual(code,0)
        queue=json.loads((Path(__file__).resolve().parents[2]/
                          "INSTANT_TASK_QUEUE.json").read_text(encoding="utf-8"))
        self.assertEqual(result["p1_code_ready_ids"],queue["first_ready"])
        self.assertEqual(result["operational_ready_count"],0)
        self.assertFalse(result["execution_allowed"])
        self.assertTrue(result["code_only"])

    def test_evidence_labels_synthetic_tests_only(self):
        code,result=invoke("evidence")
        self.assertEqual(code,0)
        self.assertEqual(result["formal_verified_rate"],"UNASSESSED")
        self.assertEqual(result["real_windows"],"NOT_RUN")
        self.assertEqual(result["independent_f18"],"SECURITY_HOLD")
        self.assertFalse(result["execution_allowed"])
        self.assertTrue(result["run_id"]>0)

    def test_stop_and_resume_never_change_protected_db_or_start_worker(self):
        for verb in ("stop","resume"):
            with self.subTest(verb=verb):
                code,result=invoke(verb,"--task-id","MLA-019")
                self.assertEqual(code,2)
                self.assertEqual(result["status"],"HOLD")
                self.assertFalse(result["task_state_changed"])
                self.assertFalse(result["execution_allowed"])

    def test_unknown_stop_target_is_redacted_error(self):
        code,result=invoke("resume","--task-id","DO_NOT_ECHO_SECRET")
        self.assertEqual(code,2)
        self.assertEqual(result["reason"],"INVALID_OR_UNAVAILABLE_LOCAL_INPUT")
        self.assertNotIn("DO_NOT_ECHO_SECRET",json.dumps(result))


if __name__ == "__main__":
    unittest.main()



class CliLocalSafetyTests(unittest.TestCase):
    def test_plan_symlink_never_read_even_for_valid_synthetic_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "target.json"
            original.write_text(json.dumps(minimal_plan()), encoding="utf-8")
            linked = Path(tmp) / "linked.json"
            try:
                linked.symlink_to(original)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            code, result = invoke("plan", "validate", "--file", str(linked))
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "HOLD")
            self.assertFalse(result["execution_allowed"])

    def test_plan_hardlink_and_linked_parent_denied(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source.json"
            source.write_text(json.dumps(minimal_plan()), encoding="utf-8")
            hard = base / "hard.json"
            os.link(source, hard)
            self.assertEqual(invoke("plan", "validate", "--file", str(hard))[0], 2)
            direct = base / "physical"
            direct.mkdir()
            file = direct / "test.json"
            file.write_text(json.dumps(minimal_plan()), encoding="utf-8")
            linked = base / "alias"
            try:
                linked.symlink_to(direct, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            self.assertEqual(invoke("plan", "validate", "--file", str(linked / "test.json"))[0], 2)

    def test_oversize_plan_refused_before_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "oversized.json"
            target.write_bytes(b"{" + b"x" * (1_048_577))
            self.assertEqual(invoke("plan", "validate", "--file", str(target))[0], 2)

    def test_queue_metric_tamper_does_not_appear_as_valid_status(self):
        import my_local_ai.cli as cli
        old_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("WORK_PHASE_GATES.json", "INSTANT_TASK_QUEUE.json"):
                shutil.copyfile(old_root / name, root / name)
            qfile = root / "INSTANT_TASK_QUEUE.json"
            queue = json.loads(qfile.read_text(encoding="utf-8"))
            queue["code_completed_req"] += 1
            qfile.write_text(json.dumps(queue), encoding="utf-8")
            with patch.object(cli, "_ROOT", root):
                for command in (("status",), ("queue", "next"), ("doctor",)):
                    with self.subTest(command=command):
                        code, result = invoke(*command)
                        self.assertEqual(code, 2)
                        self.assertEqual(result["status"], "HOLD")
                        self.assertFalse(result["execution_allowed"])



class CliPlanPreviewTests(unittest.TestCase):
    def test_offline_plan_preview_shows_dag_roots_not_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            obj = minimal_plan()
            child = json.loads(json.dumps(obj["tasks"][0]))
            child["task_id"] = "TEST-002"
            child["depends_on"] = ["TEST-001"]
            child["allowed_paths"] = ["src/child.py"]
            obj["tasks"].append(child)
            path.write_text(json.dumps(obj), encoding="utf-8")
            code, result = invoke("plan", "preview", "--file", str(path))
            self.assertEqual(code, 0)
            self.assertEqual(result["candidate_task_ids"], ["TEST-001"])
            self.assertEqual(result["reserved_calls_max"], 1)
            self.assertEqual(result["reserved_seconds_max"], 20)
            self.assertEqual(result["model_calls_executed"], 0)
            self.assertFalse(result["execution_allowed"])
            self.assertFalse(result["git_write_allowed"])
            self.assertEqual(result["independent_f18"], "SECURITY_HOLD")
            self.assertNotIn("No execution", json.dumps(result))
            self.assertNotIn("src/demo.py", json.dumps(result))

    def test_preview_cannot_expand_budget_or_start_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(minimal_plan()), encoding="utf-8")
            for params in (("--max-calls","0"),("--max-seconds","-1"),
                           ("--max-tasks","33")):
                with self.subTest(params=params):
                    code, result = invoke("plan", "preview", "--file", str(path), *params)
                    self.assertEqual(code, 2)
                    self.assertEqual(result["status"], "HOLD")

    def test_pinned_optional_eai_envelope_works_offline_only(self):
        from my_local_ai.contracts.plan import PlanSpec
        with tempfile.TemporaryDirectory() as tmp:
            plan_file = Path(tmp) / "plan.json"
            payload = minimal_plan()
            sibling = json.loads(json.dumps(payload["tasks"][0]))
            sibling["task_id"] = "TEST-002"
            sibling["allowed_paths"] = ["src/sibling.py"]
            payload["tasks"].append(sibling)
            plan_file.write_text(json.dumps(payload), encoding="utf-8")
            plan_digest = PlanSpec.parse_json(json.dumps(payload)).digest
            eai_file = Path(tmp) / "optional-eai.json"
            eai_file.write_text(json.dumps({
                "version": 1, "origin":"OPTIONAL_EAI_ADVISOR_DATA",
                "source_git_sha":SHA, "plan_sha256":plan_digest,
                "non_authoritative":True,
                "hints":[{"task_id":"TEST-002","rank":0},
                         {"task_id":"TEST-001","rank":5}],
            }), encoding="utf-8")
            code, result = invoke("plan", "preview", "--file", str(plan_file),
                                  "--eai-file", str(eai_file))
            self.assertEqual(code, 0)
            self.assertEqual(result["candidate_task_ids"], ["TEST-002","TEST-001"])
            self.assertEqual(result["advisor_status"], "OPTIONAL_HINTS_ACCEPTED")
            self.assertFalse(result["execution_allowed"])
            self.assertEqual(result["model_calls_executed"], 0)
            # Stale optional evidence must silently fall back to native ordering.
            bad = json.loads(eai_file.read_text())
            bad["plan_sha256"] = "f" * 64
            eai_file.write_text(json.dumps(bad), encoding="utf-8")
            code, fallback = invoke("plan", "preview", "--file", str(plan_file),
                                    "--eai-file", str(eai_file))
            self.assertEqual(code, 0)
            self.assertEqual(fallback["candidate_task_ids"], ["TEST-001","TEST-002"])
            self.assertEqual(fallback["advisor_status"], "INVALID_HINTS_IGNORED")


class CliMissingRequiredCommandsTests(unittest.TestCase):
    def test_plan_approve_is_digest_bound_request_and_never_creates_grant(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"plan.json"
            data=json.dumps(minimal_plan())
            target.write_text(data,encoding="utf-8")
            code,result=invoke("plan","approve","--file",str(target))
            self.assertEqual(code,2)
            self.assertEqual(result["status"],"HOLD")
            self.assertEqual(result["action"],"PLAN_APPROVE_REQUEST_ONLY")
            self.assertEqual(len(result["plan_sha256"]),64)
            self.assertFalse(result["owner_approval_verified"])
            self.assertFalse(result["signed_grant_created"])
            self.assertFalse(result["execution_allowed"])
            self.assertNotIn("src/demo.py",json.dumps(result))
            self.assertEqual(target.read_text(encoding="utf-8"),data)

    def test_queue_start_is_explicit_hold_without_state_mutation(self):
        code,result=invoke("queue","start","--task-id","MLA-006")
        self.assertEqual(code,2)
        self.assertEqual(result["status"],"HOLD")
        self.assertFalse(result["task_state_changed"])
        self.assertFalse(result["execution_allowed"])
        bad,denied=invoke("queue","start","--task-id","OTHER-999")
        self.assertEqual(bad,2)
        self.assertEqual(denied["status"],"HOLD")

    def test_benchmark_never_invents_a_real_measurement(self):
        code,report=invoke("benchmark")
        self.assertEqual(code,0)
        self.assertEqual(report["mode"],"SYNTHETIC_FIXTURE_ONLY")
        self.assertEqual(report["sample_count"],0)
        self.assertEqual(report["measured_model_calls"],0)
        self.assertIsNone(report["tokens_per_second"])
        self.assertEqual(report["real_qwen"],"NOT_RUN")
        self.assertFalse(report["execution_allowed"])

    def test_evidence_export_is_redacted_stdout_only(self):
        code,report=invoke("evidence","export")
        self.assertEqual(code,0)
        self.assertEqual(report["export_format"],"REDACTED_JSON_STDOUT_ONLY")
        self.assertFalse(report["owner_go"])
        self.assertFalse(report["real_use_allowed"])
        self.assertEqual(report["independent_f18"],"SECURITY_HOLD")


class CliDurableActionRequestSafetyTests(unittest.TestCase):
    """Immediate P1 safety check: no runtime authority from user CLI requests."""

    def test_stop_is_durable_hold_and_idempotent_without_running_worker(self):
        from my_local_ai.contracts.plan import PlanSpec
        from my_local_ai.state.sqlite_store import initialize_state, persist_local_source_task
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            plan_file = folder / "plan.json"
            raw = json.dumps(minimal_plan())
            plan_file.write_text(raw, encoding="utf-8")
            spec = PlanSpec.parse_json(raw)
            db_path = folder / "owned.sqlite3"
            initialize_state(db_path)
            persist_local_source_task(
                db_path, plan_id=spec.plan_id, task_id="TEST-001",
                plan_sha256=spec.digest, source_sha=SHA, blueprint_sha=SHA,
            )
            args = ("stop", "--task-id", "TEST-001",
                    "--plan-file", str(plan_file), "--state-db", str(db_path))
            code, result = invoke(*args)
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "HOLD")
            self.assertTrue(result["action_request_recorded"])
            self.assertTrue(result["controller_consulted"])
            self.assertTrue(result["task_state_changed"])
            self.assertFalse(result["worker_stopped"])
            self.assertFalse(result["owner_go_verified"])
            self.assertFalse(result["execution_allowed"])
            with contextlib.closing(sqlite3.connect(db_path)) as db:
                self.assertEqual(db.execute(
                    "SELECT state FROM tasks WHERE plan_id=? AND task_id=?",
                    (spec.plan_id,"TEST-001"),
                ).fetchone(), ("HOLD",))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM owner_consents").fetchone(), (0,))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM leases").fetchone(), (0,))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reviews").fetchone(), (0,))
            code2, again = invoke(*args)
            self.assertEqual(code2, 2)
            self.assertFalse(again["task_state_changed"])
            self.assertEqual(again["event_id"], result["event_id"])
            for command in (("queue", "start"), ("resume",)):
                args2 = (*command, "--task-id", "TEST-001",
                         "--plan-file", str(plan_file), "--state-db", str(db_path))
                code3, held = invoke(*args2)
                self.assertEqual(code3, 2)
                self.assertEqual(held["status"], "HOLD")
                self.assertTrue(held["controller_consulted"])
                self.assertFalse(held["execution_allowed"])
                self.assertFalse(held["task_state_changed"])

    def test_unregistered_or_tampered_plan_is_not_mutated(self):
        from my_local_ai.state.sqlite_store import initialize_state
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            file = folder / "plan.json"
            file.write_text(json.dumps(minimal_plan()), encoding="utf-8")
            db_path = folder / "owned.sqlite3"
            initialize_state(db_path)
            args = ("stop","--task-id","TEST-001",
                    "--plan-file",str(file),"--state-db",str(db_path))
            code, denied = invoke(*args)
            self.assertEqual(code, 2)
            self.assertEqual(denied["status"], "HOLD")
            self.assertFalse(denied["execution_allowed"])
            # The action must not bootstrap/approve an unknown plan.
            import sqlite3
            with contextlib.closing(sqlite3.connect(db_path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM plans").fetchone(), (0,))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone(), (0,))
