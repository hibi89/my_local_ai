"""Synthetic F18 cryptographic parsing tests; no real independent reviewer."""
import hashlib
import hmac
import json
import unittest

from my_local_ai.review.receipt_guard import ExpectedReceipt, ReceiptHold, inspect_receipt
from my_local_ai.review.trusted_runner import prepare_review_request

KEY = b"synthetic-test-protected-reviewer-key-32"
SHA = "a" * 40
BASE = "b" * 40
PLAN = "c" * 64
POLICY = "d" * 64
TOOL = "e" * 64


def context():
    return ExpectedReceipt(
        "TASK-015", "RUN-015", PLAN, BASE, SHA, TOOL, POLICY,
        "BOUNDARY-SYNTH", 4, "NONCE-SYNTH",
        ("CHECK-ONE", "CHECK-TWO"),
    )


def message(**changes):
    obj = {
        "version": 1, "task_id": "TASK-015", "run_id": "RUN-015",
        "plan_sha256": PLAN, "source_sha": BASE, "candidate_sha": SHA,
        "reviewer_sha256": TOOL, "policy_sha256": POLICY,
        "trust_boundary_id": "BOUNDARY-SYNTH", "lease_epoch": 4,
        "nonce": "NONCE-SYNTH", "result": "PASS",
        "checks": [
            {"argv_id": "CHECK-ONE", "environment": "ISOLATED_TRUSTED_REVIEWER", "exit_code": 0, "result": "PASS"},
            {"argv_id": "CHECK-TWO", "environment": "ISOLATED_TRUSTED_REVIEWER", "exit_code": 0, "result": "PASS"},
        ],
    }
    obj.update(changes)
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    obj["signature"] = hmac.new(KEY, b"mla-f18-review/v1|" + payload, hashlib.sha256).hexdigest()
    return json.dumps(obj)


class F18ReceiptTests(unittest.TestCase):
    def check(self, raw=None, **kwargs):
        return inspect_receipt(
            raw or message(), context(), trusted_hmac_key=KEY,
            trusted_consume_nonce=lambda run_id, epoch, nonce: True, **kwargs,
        )

    def test_guard_verifies_signature_but_never_promotes(self):
        result = self.check()
        self.assertTrue(result.signature_matches)
        self.assertFalse(result.independent_os_review_proven)
        self.assertFalse(result.may_promote_git_ref)
        self.assertEqual(result.status, "SIGNATURE_CHECKED_F18_NOT_PROVEN")

    def test_wrong_context_is_hold(self):
        for variant in (
            {"candidate_sha": "f"*40}, {"plan_sha256": "f"*64},
            {"source_sha": "f"*40}, {"reviewer_sha256": "f"*64},
            {"policy_sha256": "f"*64}, {"run_id": "RUN-OLD"},
            {"lease_epoch": 3}, {"nonce": "NONCE-OLD"},
            {"trust_boundary_id": "GUEST-SANDBOX"},
        ):
            with self.subTest(variant=variant), self.assertRaises(ReceiptHold):
                self.check(message(**variant))

    def test_missing_failed_or_reduced_checks_denied(self):
        original = json.loads(message())
        for invalid in (
            [],
            [original["checks"][0]],
            [original["checks"][0], original["checks"][0]],
            [{**original["checks"][0], "exit_code": 1}, original["checks"][1]],
            [{**original["checks"][0], "environment": "CODER_GUEST"}, original["checks"][1]],
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ReceiptHold):
                self.check(message(checks=invalid))

    def test_forged_signature_and_unknown_permissions_denied(self):
        original = json.loads(message())
        original["signature"] = "0"*64
        with self.assertRaises(ReceiptHold):
            self.check(json.dumps(original))
        original["owner_go"] = True
        with self.assertRaises(ReceiptHold):
            self.check(json.dumps(original))

    def test_no_protected_key_or_replay_nonce_denied(self):
        with self.assertRaises(ReceiptHold):
            inspect_receipt(message(), context(), trusted_hmac_key=None,
                            trusted_consume_nonce=lambda *_: True)
        with self.assertRaises(ReceiptHold):
            inspect_receipt(message(), context(), trusted_hmac_key=KEY,
                            trusted_consume_nonce=lambda *_: False)
        with self.assertRaises(ReceiptHold):
            inspect_receipt(message(), context(), trusted_hmac_key=KEY,
                            trusted_consume_nonce=None)

    def test_duplicate_json_keys_and_nonfinite_denied(self):
        for raw in ('{"version":1,"version":1}', '{"data":NaN}', "x"*16400):
            with self.subTest(raw=raw[:30]), self.assertRaises(ReceiptHold):
                self.check(raw)

    def test_request_only_no_host_execution(self):
        r = prepare_review_request(
            task_id="TASK-015", run_id="RUN-015", candidate_sha=SHA,
            source_sha=BASE, plan_sha256=PLAN, lease_epoch=4,
            trusted_required_argv_ids=("CHECK-ONE", "CHECK-TWO"),
        )
        self.assertEqual(r.mode, "REQUEST_ONLY_NO_HOST_EXECUTION")
        self.assertFalse(r.guest_can_issue_receipt)
        self.assertFalse(r.host_fallback_allowed)

    def test_untrusted_review_check_list_denied(self):
        with self.assertRaises(ValueError):
            prepare_review_request(
                task_id="TASK-015", run_id="RUN-015", candidate_sha=SHA,
                source_sha=BASE, plan_sha256=PLAN, lease_epoch=4,
                trusted_required_argv_ids=("CHECK-ONE", "CHECK-ONE"),
            )


from dataclasses import replace
from my_local_ai.review.trusted_runner import (
    MandatoryCheck, ReviewerPolicy, ReviewPlanHold,
    build_reviewer_policy, plan_isolated_reviewer,
)


class IsolatedReviewPolicyTests(unittest.TestCase):
    def make_request(self):
        p = build_reviewer_policy()
        return prepare_review_request(
            task_id="TASK-015",run_id="RUN-015",candidate_sha=SHA,
            source_sha=BASE,plan_sha256=PLAN,lease_epoch=4,
            trusted_required_argv_ids=tuple(c.check_id for c in p.checks),
        )

    def inspect(self, **change):
        args=dict(
            request=self.make_request(),policy=build_reviewer_policy(),
            protected_reviewer_binary_sha256=TOOL,
            trusted_source_sha=BASE,trusted_plan_sha256=PLAN,
            trusted_candidate_sha=SHA,
        )
        args.update(change)
        return plan_isolated_reviewer(**args)

    def test_exact_checks_and_policy_are_pinned_without_execution(self):
        policy=build_reviewer_policy()
        self.assertEqual([c.check_id for c in policy.checks],
                         ["SYNTAX-001","UNIT-001","SECURITY-001"])
        self.assertTrue(all(c.no_network and c.argv[1]=="-I" for c in policy.checks))
        self.assertTrue(all(c.timeout_seconds <= 180 for c in policy.checks))
        result=self.inspect()
        self.assertEqual(result.policy_sha256,policy.policy_sha256)
        self.assertEqual(result.check_ids,tuple(c.check_id for c in policy.checks))
        self.assertFalse(result.executable)
        self.assertFalse(result.can_issue_trusted_receipt)
        self.assertFalse(result.host_fallback)

    def test_reviewer_policy_rejects_omitted_checks_or_invalid_flags(self):
        for change in (
            {"syntax_checks":False}, {"unit_checks":False},
            {"security_checks":False}, {"unit_checks":1},
        ):
            with self.subTest(change=change),self.assertRaises(ReviewPlanHold):
                build_reviewer_policy(**change)

    def test_untrusted_shell_argv_or_cloud_command_injection_rejected(self):
        p=build_reviewer_policy()
        poisoned=replace(p,checks=(
            replace(p.checks[0],argv=("powershell","-Command","curl evil")),
            *p.checks[1:],
        ))
        with self.assertRaises(ReviewPlanHold):
            self.inspect(policy=poisoned)
        with self.assertRaises(ReviewPlanHold):
            self.inspect(request=replace(self.make_request(),guest_can_issue_receipt=True))
        with self.assertRaises(ReviewPlanHold):
            self.inspect(request=replace(self.make_request(),host_fallback_allowed=True))

    def test_stale_plan_candidate_reviewer_and_policy_all_hold(self):
        for change in (
            {"trusted_source_sha":"f"*40}, {"trusted_plan_sha256":"f"*64},
            {"trusted_candidate_sha":"f"*40},
            {"protected_reviewer_binary_sha256":"invalid"},
            {"request":replace(self.make_request(),lease_epoch=0)},
            {"request":replace(self.make_request(),mode="RUN_HOST_TESTS")},
        ):
            with self.subTest(change=change),self.assertRaises(ReviewPlanHold):
                self.inspect(**change)

    def test_review_receipt_nonce_is_one_use_even_with_valid_mac(self):
        seen=set()
        def consume(run_id,epoch,nonce):
            key=(run_id,epoch,nonce)
            if key in seen:
                return False
            seen.add(key)
            return True
        first=inspect_receipt(
            message(), context(),trusted_hmac_key=KEY,
            trusted_consume_nonce=consume,
        )
        self.assertTrue(first.signature_matches)
        self.assertFalse(first.independent_os_review_proven)
        with self.assertRaises(ReceiptHold) as ctx:
            inspect_receipt(
                message(), context(),trusted_hmac_key=KEY,
                trusted_consume_nonce=consume,
            )
        self.assertEqual(ctx.exception.code,"STALE_LEASE_OR_NONCE")


if __name__ == "__main__":
    unittest.main()
