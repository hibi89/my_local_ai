"""No external execution or network in these tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from unittest.mock import patch
import unittest

from my_local_ai.ax_runtime import approved_workflow as workflow
from my_local_ai.ax_runtime.manual_draft import LocalDrafts, _HandoffContext, _WorkQueue
from my_local_ai.ax_runtime.draft_documents import DraftDocument, DraftError
from my_local_ai.ax_runtime.draft_intake import handoff_tasks, parse_handoff

SHA = "a"*40
MESSAGE = """Repository: hibi89/REQ-Evidence-Auditor-A-
Branch: integration/reqea-p1-20261118
### P2-A. 백엔드 CLI 통합 테스트
실제 Python 실행 테스트
### P2-E. GitHub Actions 실제 수동 실행
승인된 기존 수동 워크플로 실제 실행과 기록
"""


class TestApprovedWorkflow(unittest.TestCase):
    def test_exact_profile_only(self):
        self.assertTrue(workflow.eligible_profile(workflow.REPO, workflow.BRANCH, SHA,
                                                "P2-E. GitHub Actions 실제 수동 실행"))
        for repo, branch, sha, title in (
            ("other/repo", workflow.BRANCH, SHA, "P2-E. GitHub Actions 실제 수동 실행"),
            (workflow.REPO, "main", SHA, "P2-E. GitHub Actions 실제 수동 실행"),
            (workflow.REPO, workflow.BRANCH, "bad", "P2-E. GitHub Actions 실제 수동 실행"),
            (workflow.REPO, workflow.BRANCH, SHA, "P2-A. 통합 검증"),
        ):
            self.assertFalse(workflow.eligible_profile(repo, branch, sha, title))

    def test_dispatch_once_and_reconcile_one_real_run_receipt(self):
        receipts, calls = [], []
        def api(path, *, fields=(), method="GET"):
            calls.append((path, fields, method))
            if "/commits/" in path: return {"sha": SHA}
            if "/contents/" in path: return {"sha": workflow.WORKFLOW_BLOB}
            if path.endswith("/dispatches"): return None
            if "/runs?" in path:
                from datetime import datetime, timezone
                return {"workflow_runs": [{
                    "id": 789, "head_sha": SHA, "head_branch": workflow.BRANCH,
                    "event": "workflow_dispatch",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "completed", "conclusion": "success",
                }]}
            self.fail(path)
        with patch.object(workflow, "_gh_api", side_effect=api):
            workflow.execute_once(SHA, receipts.append, poll_interval=0, max_polls=1)
        self.assertEqual([r["state"] for r in receipts], ["DISPATCHING", "RUNNING", "PASS"])
        self.assertEqual(len([v for v in calls if v[2] == "POST"]), 1)
        self.assertEqual(receipts[-1]["run_id"], 789)
        self.assertFalse(receipts[-1]["p2_gate_accepted"])
        self.assertFalse(receipts[-1]["independent_verified"])
        self.assertIsNone(receipts[-1]["exit_code"])

    def test_stale_branch_and_ambiguous_run_hold_without_false_success(self):
        receipts = []
        with patch.object(workflow, "_read_branch_head", return_value="b"*40), patch.object(
            workflow, "_gh_api") as transport:
            workflow.execute_once(SHA, receipts.append)
        self.assertEqual(receipts[-1]["code"], "HOLD_SOURCE_MOVED")
        transport.assert_not_called()
        receipts.clear()
        with patch.object(workflow, "_read_branch_head", return_value=SHA), patch.object(
            workflow, "_verify_workflow_blob"), patch.object(
            workflow, "_gh_api", return_value=None), patch.object(
            workflow, "_find_run", return_value=[{"id": 1}, {"id": 2}]):
            workflow.execute_once(SHA, receipts.append, poll_interval=0, max_polls=1)
        self.assertEqual(receipts[-1]["code"], "HOLD_AMBIGUOUS_RUN_ID")

    @staticmethod
    def make_app(root):
        app = LocalDrafts(root)
        scope = parse_handoff(MESSAGE)
        plan = {"repository": scope.repository, "workspace": scope.workspace, "revision": SHA}
        queue = _WorkQueue("e"*24, handoff_tasks(MESSAGE),
                           _HandoffContext(DraftDocument(MESSAGE, "paste"), [],
                                           {}, {}, plan, scope))
        key = queue.items[1].key
        queue.inspections[key] = {"state": "observed", "revision": SHA, "remaining": "real",
                                  "files": [], "notes": []}
        app._queue = queue
        app._state["state"] = "ready"
        return app, key

    def test_persistent_once_only_launch_and_no_p2_promotion(self):
        with TemporaryDirectory() as folder:
            app, key = self.make_app(Path(folder).resolve() / "drafts")
            def runner(sha, callback):
                callback({"state": "PASS", "run_id": 789,
                          "p2_gate_accepted": False, "independent_verified": False})
            with patch("my_local_ai.ax_runtime.manual_draft.execute_once", side_effect=runner) as run:
                app.start({"queue": "e"*24, "execute": "reqea-manual", "item": key})
                for _ in range(100):
                    report = app.snapshot()["work_queue"]["items"][1]["execution"]
                    if report and report["state"] == "PASS": break
                    sleep(0.01)
                else: self.fail("no persisted run")
                with self.assertRaises(DraftError):
                    app.start({"queue": "e"*24, "execute": "reqea-manual", "item": key})
            run.assert_called_once()
            self.assertEqual(app.snapshot()["work_queue"]["executed_count"], 1)
            self.assertEqual(app.snapshot()["work_queue"]["verified_count"], 0)
            restored = LocalDrafts(app.root).snapshot()["work_queue"]
            self.assertEqual(restored["items"][1]["execution"]["run_id"], 789)
            self.assertFalse(restored["items"][1]["can_execute"])

    def test_interrupted_intent_never_auto_redispatches(self):
        with TemporaryDirectory() as folder:
            app, key = self.make_app(Path(folder).resolve() / "drafts")
            app._queue.executions[key] = workflow.initial_receipt(SHA)
            app._checkpoint_locked(replace=True)
            restored = LocalDrafts(app.root).snapshot()["work_queue"]
            report = restored["items"][1]["execution"]
            self.assertEqual(report["code"], "HOLD_INTERRUPTED_NO_REDISPATCH")
            self.assertFalse(restored["items"][1]["can_execute"])

    def test_other_part_cannot_launch(self):
        with TemporaryDirectory() as folder:
            app, _ = self.make_app(Path(folder).resolve() / "drafts")
            with patch("my_local_ai.ax_runtime.manual_draft.execute_once") as dispatch:
                with self.assertRaises(DraftError):
                    app.start({"queue": "e"*24, "execute": "reqea-manual",
                               "item": app._queue.items[0].key})
            dispatch.assert_not_called()
