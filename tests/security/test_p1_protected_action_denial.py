"""Immediate P1 safety checks for newly authored protected action paths.

Synthetic-only: no network, model, Git mutation or real OS/F18 grant.
These checks prove the default denial, NOT the future protected runtime.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from my_local_ai.gitops.local_integration import (
    IntegrationHold, LocalCASIntent, persist_protected_local_ref_cas,
)
from my_local_ai.gitops.remote_preview import DraftPRPreview
from my_local_ai.gitops.remote_publish import (
    DraftPublishHold, prepare_draft_action_intent,
    publish_action_bound_draft_pr,
)
from my_local_ai.orchestrator import persist_controller_review_hold_cycle
from my_local_ai.app import build_controller_hold_cycle_card
from my_local_ai.contracts.plan import PlanSpec
from my_local_ai.state.sqlite_store import initialize_state, persist_local_source_task

A = "a" * 40
B = "b" * 40
F = "f" * 64


def _minimal_plan():
    return {
        "version": 1, "plan_id": "TEST-001",
        "blueprint": {"repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1", "sha": A},
        "approval": {"status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None},
        "tasks": [{
            "task_id": "TEST-001", "req_ids": ["REQ-09"], "depends_on": [],
            "goal": "HOLD only", "allowed_paths": ["src/demo.py"],
            "acceptance": ["reviewed"], "checks": [], "risk": "LOW",
            "resource_budget": {"max_calls": 1, "max_seconds": 20},
            "safety_checks": ["NO_REMOTE"], "plan_sha": None, "source_sha": A,
        }],
    }


class ProtectedActionHardDenialTests(unittest.TestCase):
    def test_local_ref_writer_denies_os_change_before_any_protected_callback(self):
        called = []
        def forbidden(*a, **kw):
            called.append((a,kw))
            raise AssertionError("protected Git callback invoked before owner GO")
        intent = LocalCASIntent(
            "refs/heads/mla/isolated/TEST-001", A, B, A, "TEST-001",
        )
        with self.assertRaises(IntegrationHold):
            persist_protected_local_ref_cas(
                "/unused/original", intent=intent,
                plan_sha256=F, trusted_source_sha=A,
                expected_main_sha=A, lease_epoch=1,
                owner_grant=None, trusted_hmac_key=None,
                trusted_live_consent_check=forbidden, now_seconds=1,
                protected_lease_epoch_check=forbidden,
                protected_f18_review_check=forbidden,
                protected_git_read=forbidden, protected_git_write=forbidden,
            )
        self.assertEqual(called, [])

    def test_draft_pr_denies_remote_action_before_all_network_ports(self):
        called = []
        def forbidden(*a, **kw):
            called.append((a,kw))
            raise AssertionError("network port invoked without remote owner GO")
        draft = DraftPRPreview(
            repository="hibi89/my_local_ai", base_branch="main",
            expected_base_sha=A, source_sha=A, candidate_sha=B,
            changed_file_count=1,
            target_local_ref="refs/heads/mla/review/TEST-001",
            change_paths_sha256=F,
        )
        intent = prepare_draft_action_intent(draft)
        with self.assertRaises(DraftPublishHold):
            publish_action_bound_draft_pr(
                draft, intent, plan_sha256=F,
                owner_grant=None, trusted_hmac_key=None,
                trusted_live_consent_check=forbidden,
                now_seconds=1,
                protected_f18_acceptance=forbidden,
                protected_remote_readback=forbidden,
                protected_push_new_ref=forbidden,
                protected_create_draft_pr=forbidden,
            )
        self.assertEqual(called, [])


class ControllerHoldCycleTests(unittest.TestCase):
    def test_controller_f18_request_persists_only_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=root/"original"
            worktree=root/"disposable"
            original.mkdir()
            worktree.mkdir()
            db=root/"owned.sqlite3"
            initialize_state(db)
            raw=json.dumps(_minimal_plan())
            plan=PlanSpec.parse_json(raw)
            persist_local_source_task(
                db, plan_id=plan.plan_id, task_id="TEST-001",
                plan_sha256=plan.digest, source_sha=A, blueprint_sha=A,
            )
            with sqlite3.connect(db) as connection:
                connection.execute(
                    "UPDATE tasks SET state='READY' "
                    "WHERE plan_id='TEST-001' AND task_id='TEST-001'"
                )
            result=persist_controller_review_hold_cycle(
                db, plan_json=raw, task_id="TEST-001",
                disposable_worktree=worktree,
                original_checkout=original, run_id="RUN-001",
                candidate_sha=B, reviewer_binary_sha256_claim=F,
                lease_epoch=1,
            )
            self.assertEqual(result.state,"HOLD_F18_INDEPENDENCE_NOT_ESTABLISHED")
            self.assertTrue(result.task_state_changed)
            self.assertFalse(result.coder_executed)
            self.assertFalse(result.reviewer_executed)
            self.assertFalse(result.trusted_receipt_issued)
            view=build_controller_hold_cycle_card(result)
            self.assertFalse(view["execution_allowed"])
            self.assertEqual(view["reviewer_result"],"NOT_RUN")
            with sqlite3.connect(db) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT state FROM tasks WHERE plan_id='TEST-001' "
                        "AND task_id='TEST-001'",
                    ).fetchone(), ("HOLD",),
                )
                for table in ("leases","runs","owner_consents","reviews","integrations"):
                    self.assertEqual(
                        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone(),
                        (0,),
                    )
            # Replays cannot silently reissue a coder lease or reviewer PASS.
            with self.assertRaises(ValueError):
                persist_controller_review_hold_cycle(
                    db, plan_json=raw, task_id="TEST-001",
                    disposable_worktree=worktree,
                    original_checkout=original, run_id="RUN-001",
                    candidate_sha=B, reviewer_binary_sha256_claim=F,
                    lease_epoch=1,
                )


if __name__ == "__main__":
    unittest.main()
