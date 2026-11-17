"""P1 synthetic CLI tests; must have zero side effects."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

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
