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


from my_local_ai.ax_runtime.recovery import plan_improved_repair


class ImprovedRepairPolicyTests(unittest.TestCase):
    def plan(self,**change):
        values=dict(
            checkpoint=checkpoint(),
            failed_check="UNIT_FAILURE",
            failure_fingerprint_sha256="e"*64,
            previous_strategy="LIMITED_SYNTAX_REPAIR",
            proposed_strategy="ISOLATED_UNIT_FIX",
            observed_epoch=42,plan_sha256=PLAN,source_sha=BASE,
        )
        values.update(change)
        return plan_improved_repair(**values)

    def test_one_improved_retry_requires_new_lease_and_owner_go(self):
        r=self.plan()
        self.assertEqual(r.attempt_number,2)
        self.assertEqual(r.minimum_next_epoch,43)
        self.assertEqual(r.new_strategy,"ISOLATED_UNIT_FIX")
        self.assertFalse(r.auto_retry)
        self.assertFalse(r.may_run_on_host)
        self.assertFalse(r.may_mark_verified)

    def test_identical_retry_or_same_failure_without_improvement_denied(self):
        with self.assertRaises(ValueError):
            self.plan(proposed_strategy="LIMITED_SYNTAX_REPAIR")
        with self.assertRaises(ValueError):
            self.plan(proposed_strategy="RUN_ARBITRARY_SHELL")
        with self.assertRaises(ValueError):
            self.plan(failed_check="SELF_VERIFIED")

    def test_second_failure_exhaustion_denied(self):
        with self.assertRaises(ValueError):
            self.plan(checkpoint=checkpoint(attempts_used=2))
        with self.assertRaises(ValueError):
            self.plan(checkpoint=checkpoint(attempts_used=0))

    def test_stale_plan_source_epoch_or_untrusted_candidate_denied(self):
        for change in (
            {"observed_epoch":41},
            {"plan_sha256":"f"*64},
            {"source_sha":"f"*40},
            {"checkpoint":checkpoint(candidate_sha=None)},
            {"failure_fingerprint_sha256":"wrong"},
        ):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.plan(**change)


if __name__ == "__main__":
    unittest.main()



class RepairLoopPreventionTests(unittest.TestCase):
    def test_cannot_reenter_repair_once_checkpoint_even_with_attempt_one(self):
        unusual = checkpoint(state="REPAIR_ONCE", attempts_used=1)
        response = decide(unusual)
        self.assertEqual(response.state, "HOLD")
        self.assertIsNone(response.next_attempt)
        with self.assertRaises(ValueError):
            plan_improved_repair(
                unusual, failed_check="UNIT_FAILURE",
                failure_fingerprint_sha256="e" * 64,
                previous_strategy="LIMITED_SYNTAX_REPAIR",
                proposed_strategy="ISOLATED_UNIT_FIX",
                observed_epoch=42, plan_sha256=PLAN, source_sha=BASE,
            )

    def test_failed_review_without_candidate_cannot_get_repair_budget(self):
        response = decide(checkpoint(candidate_sha=None))
        self.assertEqual(response.state, "HOLD")
        self.assertFalse(response.runnable)

    def test_strategy_change_must_match_actual_failure_category(self):
        original = checkpoint()
        for failure, inappropriate in (
            ("SYNTAX_ERROR", "REDUCE_BATCH_MEMORY"),
            ("UNIT_FAILURE", "NARROW_PERMISSION_FIX"),
            ("SECURITY_FAILURE", "REDUCE_BATCH_MEMORY"),
            ("CONTRACT_FAILURE", "LIMITED_SYNTAX_REPAIR"),
            ("SANDBOX_TIMEOUT", "ISOLATED_UNIT_FIX"),
        ):
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                plan_improved_repair(
                    original, failed_check=failure,
                    failure_fingerprint_sha256="e" * 64,
                    previous_strategy="CONTRACT_SCOPE_CORRECTION",
                    proposed_strategy=inappropriate,
                    observed_epoch=42, plan_sha256=PLAN, source_sha=BASE,
                )

    def test_timeout_repair_is_specific_and_never_self_runs(self):
        out = plan_improved_repair(
            checkpoint(), failed_check="SANDBOX_TIMEOUT",
            failure_fingerprint_sha256="f" * 64,
            previous_strategy="ISOLATED_UNIT_FIX",
            proposed_strategy="REDUCE_BATCH_MEMORY",
            observed_epoch=42, plan_sha256=PLAN, source_sha=BASE,
        )
        self.assertEqual(out.new_strategy, "REDUCE_BATCH_MEMORY")
        self.assertFalse(out.auto_retry)
        self.assertFalse(out.may_mark_verified)
