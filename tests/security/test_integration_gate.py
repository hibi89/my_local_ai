"""No real Git updates: synthetic CAS shape and F18 HOLD tests."""
from dataclasses import replace
import unittest

from my_local_ai.gitops.local_integration import (
    RefSnapshot,LocalCASIntent,IntegrationHold,plan_isolated_local_cas,
)
from my_local_ai.review.receipt_guard import ReceiptInspection

SHA0="a"*40
SHA1="b"*40
CAND="c"*40


def baseline(**changes):
    args=dict(
        target_local_ref="refs/heads/mla/isolated/TASK-018",
        expected_old_sha=SHA0,actual_old_sha=SHA0,
        owner_original_sha=SHA1,original_readback_sha=SHA1,
    )
    args.update(changes)
    return RefSnapshot(**args)


def review(**changes):
    args=dict(task_id="TASK-018",candidate_sha=CAND,signature_matches=True)
    args.update(changes)
    return ReceiptInspection(**args)


def propose(**changes):
    args=dict(task_id="TASK-018",candidate_sha=CAND,
              snapshot=baseline(),inspection=review())
    args.update(changes)
    return plan_isolated_local_cas(**args)


class LocalGitCASGateTests(unittest.TestCase):
    def test_signature_only_still_f18_hold(self):
        with self.assertRaises(IntegrationHold) as ctx:
            propose(trusted_owner_grant_present=True)
        self.assertEqual(ctx.exception.code,"F18_NOT_INDEPENDENT")

    def test_untrusted_attestation_flags_never_make_operation_executable(self):
        forged=replace(review(),independent_os_review_proven=True,
                       may_promote_git_ref=True)
        intent=propose(inspection=forged,trusted_owner_grant_present=True)
        self.assertEqual(intent.state,"HOLD_PENDING_INDEPENDENT_F18_AND_OWNER_GO")
        self.assertFalse(intent.executable)
        self.assertFalse(intent.may_write_ref)
        self.assertFalse(intent.may_write_original)
        self.assertFalse(intent.may_push_remote)

    def test_owner_false_holds_even_with_claimed_f18(self):
        forged=replace(review(),independent_os_review_proven=True,
                       may_promote_git_ref=True)
        with self.assertRaises(IntegrationHold) as ctx:
            propose(inspection=forged)
        self.assertEqual(ctx.exception.code,"MISSING_OWNER_GO")

    def test_main_remote_and_unsafe_ref_denied(self):
        for ref in ("refs/heads/main","refs/heads/master","refs/remotes/origin/main",
                    "refs/heads/mla/isolated/../main",
                    "refs/heads/mla/isolated/TASK-018.lock",
                    "refs/tags/v1","refs/heads/mla/isolated/ma/in",
                    "refs/heads/mla/isolated/a"):
            with self.subTest(ref=ref),self.assertRaises(IntegrationHold):
                propose(snapshot=baseline(target_local_ref=ref))

    def test_cas_race_original_rewrite_and_bad_candidate_denied(self):
        for snap in (
            baseline(actual_old_sha="f"*40),
            baseline(original_readback_sha="f"*40),
            baseline(actual_old_sha=CAND,expected_old_sha=CAND),
            baseline(owner_original_sha=CAND,original_readback_sha=CAND),
        ):
            with self.subTest(snap=snap),self.assertRaises(IntegrationHold):
                propose(snapshot=snap)
        with self.assertRaises(IntegrationHold):
            propose(candidate_sha="short")

    def test_wrong_or_missing_review_denied(self):
        for inspection in (
            None,review(candidate_sha="f"*40),
            review(task_id="OTHER-018"),review(signature_matches=False),
        ):
            with self.subTest(i=inspection),self.assertRaises(IntegrationHold):
                propose(inspection=inspection)

    def test_no_git_subprocess_or_branch_mutation_port(self):
        forged=replace(review(),independent_os_review_proven=True,
                       may_promote_git_ref=True)
        v=propose(inspection=forged,trusted_owner_grant_present=True)
        self.assertIsInstance(v,LocalCASIntent)
        self.assertEqual(v.target_local_ref,"refs/heads/mla/isolated/TASK-018")
        self.assertNotIn("cmd",v.__dict__)
        self.assertNotIn("execute",v.__dict__)


if __name__=="__main__":
    unittest.main()
