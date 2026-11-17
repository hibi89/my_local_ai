"""Synthetic BE+FE read-only integration, with EAI OFF and untrusted outputs."""
import json
from pathlib import Path
import unittest

from my_local_ai.orchestrator import preview_plan,redact_preview
from my_local_ai.app import build_read_only_app

ROOT=Path(__file__).resolve().parents[2]
SOURCE="a"*40


def plan():
    def task(id,deps=()):
        return {
            "task_id":id,"req_ids":["REQ-05"],
            "depends_on":list(deps),"goal":"SENSITIVE_CODING_PROMPT_CANARY",
            "allowed_paths":["src/synthetic.py"],"acceptance":["synthetic"],
            "checks":[],"risk":"LOW",
            "resource_budget":{"max_calls":1,"max_seconds":30},
            "safety_checks":["NO_REMOTE"],"plan_sha":None,
            "source_sha":SOURCE,
        }
    return json.dumps({
        "version":1,"plan_id":"SYNTH-019",
        "blueprint":{"repo":"hibi89/my_local_ai",
                     "branch":"dev/instant-implementation-v1","sha":SOURCE},
        "approval":{"status":"NOT_APPROVED","scope":"SYNTHETIC_ONLY","digest":None},
        "tasks":[task("TASK-019-A"),task("TASK-019-B",("TASK-019-A",))],
    })


class SyntheticJourneyTests(unittest.TestCase):
    def setUp(self):
        self.states={"TASK-019-A":"READY","TASK-019-B":"READY"}

    def test_native_controller_to_public_app_no_original_eai(self):
        result=build_read_only_app(
            project_root=ROOT,plan_json=plan(),
            protected_states=self.states,advisory_json=None,
        )
        summary=result.to_public_dict()
        self.assertEqual(summary["planning"]["candidate_task_ids"],["TASK-019-A"])
        self.assertEqual(summary["planning"]["advisory_status"],"DISABLED")
        self.assertFalse(summary["execution_allowed"])
        self.assertEqual(summary["implementation"]["total_req"],30)
        self.assertTrue(summary["implementation"]["p2_locked"])

    def test_no_sensitive_plan_content_in_frontend_response(self):
        public=build_read_only_app(
            project_root=ROOT,plan_json=plan(),protected_states=self.states,
        ).to_public_dict()
        serialized=json.dumps(public)
        self.assertNotIn("SENSITIVE_CODING_PROMPT_CANARY",serialized)
        self.assertNotIn("src/synthetic.py",serialized)
        self.assertNotIn("KEY=",serialized)

    def test_coder_self_verified_label_does_not_unlock_child(self):
        self.states["TASK-019-A"]="VERIFIED"
        preview=preview_plan(plan_json=plan(),protected_states=self.states)
        self.assertEqual(preview.candidate_task_ids,())
        with_f18_claim=preview_plan(plan_json=plan(),protected_states=self.states,
                                    independently_verified={"TASK-019-A"})
        self.assertEqual(with_f18_claim.candidate_task_ids,("TASK-019-B",))
        self.assertFalse(with_f18_claim.can_run_coder)
        self.assertFalse(with_f18_claim.f18_independently_verified)

    def test_advisory_injection_does_not_change_actions(self):
        injected='{"version":1,"hints":[],"execute":"powershell -nop"}'
        out=preview_plan(plan_json=plan(),protected_states=self.states,advisory_json=injected)
        self.assertEqual(out.advisory_status,"INVALID_HINTS_IGNORED")
        self.assertFalse(out.can_publish_remote)
        self.assertEqual(out.candidate_task_ids,("TASK-019-A",))

    def test_duplicate_lease_suppresses_ready(self):
        out=preview_plan(plan_json=plan(),protected_states=self.states,
                         active_leases={"TASK-019-A"})
        self.assertEqual(out.candidate_task_ids,())

    def test_unknown_state_or_invalid_plan_refused(self):
        with self.assertRaises(ValueError):
            preview_plan(plan_json=plan(),protected_states={})
        with self.assertRaises(ValueError):
            preview_plan(plan_json="{bad json",protected_states=self.states)


if __name__=="__main__":
    unittest.main()
