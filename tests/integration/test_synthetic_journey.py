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


from dataclasses import replace
from tempfile import TemporaryDirectory
from my_local_ai.orchestrator import preview_local_code_request
from my_local_ai.app import safe_code_request_card


class SyntheticControllerWorkerJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.original=self.root/"original"
        self.worktree=self.root/"disposable"
        self.original.mkdir()
        self.worktree.mkdir()
        self.states={"TASK-019-A":"READY","TASK-019-B":"READY"}

    def worker(self, **changes):
        params=dict(plan_json=plan(),protected_states=self.states,
                    task_id="TASK-019-A",disposable_worktree=self.worktree,
                    original_checkout=self.original)
        params.update(changes)
        return preview_local_code_request(**params)

    def test_full_native_controller_to_local_code_request_is_nonexecuting(self):
        result=self.worker()
        card=safe_code_request_card(result)
        self.assertEqual(card["task_id"],"TASK-019-A")
        self.assertEqual(card["provider"],"LOCAL_QWEN_OPENCODE")
        self.assertEqual(card["allowed_file_count"],1)
        self.assertEqual(card["stage"],"CODE_REQUEST_PREPARED_ONLY")
        self.assertEqual(card["review_status"],"F18_HOLD")
        self.assertFalse(card["execution_allowed"])
        self.assertFalse(card["network_allowed"])
        self.assertFalse((self.worktree/"src/synthetic.py").exists())

    def test_no_model_prompt_or_allowed_paths_in_public_payload(self):
        preview=self.worker()
        raw=json.dumps(safe_code_request_card(preview))
        self.assertNotIn("SENSITIVE_CODING_PROMPT_CANARY",raw)
        self.assertNotIn("src/synthetic.py",raw)
        self.assertNotIn("OPENCODE_CONFIG_CONTENT",raw)
        self.assertNotIn("SYNTHETIC NONEXECUTING REQUEST",raw)

    def test_unverified_dependency_or_active_lease_is_not_worker_candidate(self):
        with self.assertRaises(ValueError):
            self.worker(task_id="TASK-019-B")
        with self.assertRaises(ValueError):
            self.worker(active_leases={"TASK-019-A"})
        self.states["TASK-019-A"]="VERIFIED"
        with self.assertRaises(ValueError):
            self.worker()

    def test_advisor_cannot_force_task_without_dag(self):
        injected='{"version":1,"hints":[{"task_id":"TASK-019-B","rank":0}]}'
        with self.assertRaises(ValueError):
            self.worker(task_id="TASK-019-B",advisory_json=injected)

    def test_bad_or_non_isolated_worktree_refused(self):
        with self.assertRaises(Exception):
            self.worker(disposable_worktree=self.original)
        with self.assertRaises(Exception):
            self.worker(disposable_worktree=self.root/"missing")
        self.assertEqual(list(self.original.iterdir()),[])

    def test_claimed_owner_go_cannot_modify_worker_card(self):
        original=self.worker()
        for tampered in (
            replace(original,owner_signed_go=True),
            replace(original,may_execute=True),
            replace(original,code_worker_executed=True),
            replace(original,real_isolation_verified=True),
            replace(original,candidate_verified=True),
        ):
            with self.subTest(tampered=tampered),self.assertRaises(ValueError):
                safe_code_request_card(tampered)


if __name__=="__main__":
    unittest.main()
