"""Synthetic pure repair-once policy: no execution, no private data."""
from dataclasses import replace
import unittest

from my_local_ai.ax_runtime.recovery import (
    RecoveryCheckpoint, propose_recovery,
)

PLAN = "a" * 64
BASE = "b" * 40


def checkpoint(**kwargs):
    args = dict(run_id="RUN-001", task_id="TASK-016", plan_sha=PLAN,
                baseline_sha=BASE, lease_epoch=42, attempts_used=1,
                candidate_sha="c"*40, state="REVIEW_PENDING")
    args.update(kwargs)
    return RecoveryCheckpoint(**args)


def decide(cp=None, **options):
    values = dict(event="REVIEW_FAILED", expected_plan_sha=PLAN,
                  expected_baseline_sha=BASE, observed_lease_epoch=42)
    values.update(options)
    return propose_recovery(cp or checkpoint(), **values)


class RecoveryPolicyTests(unittest.TestCase):
    def test_one_repair_only_and_never_executes(self):
        answer = decide()
        self.assertEqual(answer.state, "REPAIR_ONCE")
        self.assertEqual(answer.next_attempt, 2)
        self.assertEqual(answer.minimum_next_lease_epoch, 43)
        self.assertTrue(answer.requires_new_owner_grant)
        self.assertFalse(answer.runnable)
        self.assertFalse(answer.verified)

    def test_second_failure_and_missing_previous_attempt_hold(self):
        for attempts in (0, 2):
            with self.subTest(attempts=attempts):
                answer = decide(checkpoint(attempts_used=attempts))
                self.assertEqual(answer.state, "HOLD")
                self.assertIsNone(answer.next_attempt)

    def test_untrusted_self_pass_cannot_promote(self):
        response = decide(event="REVIEW_PASSED_CLAIM")
        self.assertEqual(response.state, "HOLD")
        self.assertFalse(response.verified)

    def test_model_boolean_cannot_claim_independent_pass(self):
        with self.assertRaises(ValueError):
            decide(independently_accepted_candidate=True)

    def test_stale_plan_baseline_or_lease_are_refused(self):
        for change in ({"expected_plan_sha": "0"*64},
                       {"expected_baseline_sha": "0"*40},
                       {"observed_lease_epoch": 41},
                       {"observed_lease_epoch": 43}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                decide(**change)

    def test_interrupted_run_requires_new_lease_and_grant(self):
        answer = decide(event="CODER_INTERRUPTED")
        self.assertEqual(answer.state, "INTERRUPTED")
        self.assertTrue(answer.requires_new_owner_grant)
        self.assertEqual(answer.minimum_next_lease_epoch, 43)
        self.assertFalse(answer.runnable)

    def test_review_pending_cannot_auto_approve(self):
        answer = decide(event="REVIEW_PENDING")
        self.assertEqual(answer.state, "HOLD")
        self.assertFalse(answer.requires_new_owner_grant)
        self.assertFalse(answer.verified)

    def test_illegal_checkpoint_rejected(self):
        for change in ({"lease_epoch": 0}, {"attempts_used": 3},
                       {"task_id": "../secret"}, {"candidate_sha": "forged"},
                       {"state": "VERIFIED"}, {"plan_sha": "not-a-digest"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                checkpoint(**change)

    def test_mismatched_state_or_event_denied(self):
        self.assertEqual(decide(checkpoint(state="CODING")).state, "HOLD")
        with self.assertRaises(ValueError):
            decide(event="MERGE_TO_MAIN")


if __name__ == "__main__":
    unittest.main()
