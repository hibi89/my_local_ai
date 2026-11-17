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


class SyntheticCASStateMachineTests(unittest.TestCase):
    def intent(self):
        return LocalCASIntent(
            "refs/heads/mla/isolated/TASK-018", SHA0, CAND, SHA1, "TASK-018",
        )

    def store(self):
        from my_local_ai.gitops.local_integration import SyntheticIsolatedRefStore
        return SyntheticIsolatedRefStore(
            {"refs/heads/mla/isolated/TASK-018": SHA0},
            owner_original_sha=SHA1, main_sha="d"*40,
        )

    def test_atomic_cas_updates_only_synthetic_isolated_ref(self):
        store=self.store()
        original,main=store.original_sha,store.main_sha
        receipt=store.synthetic_compare_swap(self.intent(),expected_main_sha=main)
        self.assertEqual(receipt.status,"SYNTHETIC_MEMORY_ONLY_NOT_VERIFIED")
        self.assertEqual(store.read(self.intent().target_local_ref),CAND)
        self.assertEqual(store.original_sha,original)
        self.assertEqual(store.main_sha,main)
        self.assertFalse(receipt.f18_verified)
        self.assertFalse(receipt.may_push_remote)

    def test_second_worker_cannot_reuse_old_ref_generation(self):
        store=self.store()
        store.synthetic_compare_swap(self.intent(),expected_main_sha=store.main_sha)
        with self.assertRaises(IntegrationHold) as ctx:
            store.synthetic_compare_swap(self.intent(),expected_main_sha=store.main_sha)
        self.assertEqual(ctx.exception.code,"SHA_MISMATCH")
        self.assertEqual(store.read(self.intent().target_local_ref),CAND)

    def test_main_or_original_sha_race_preserves_ref(self):
        store=self.store()
        with self.assertRaises(IntegrationHold):
            store.synthetic_compare_swap(self.intent(),expected_main_sha="f"*40)
        with self.assertRaises(IntegrationHold):
            store.synthetic_compare_swap(
                replace(self.intent(),owner_original_sha="f"*40),
                expected_main_sha=store.main_sha,
            )
        self.assertEqual(store.read(self.intent().target_local_ref),SHA0)

    def test_forged_permission_bools_cannot_become_operating_right(self):
        store=self.store()
        for changes in (
            {"executable":True},{"may_write_ref":True},{"may_write_original":True},
            {"may_push_remote":True},{"state":"VERIFIED"},
            {"target_local_ref":"refs/heads/main"},
        ):
            with self.subTest(changes=changes),self.assertRaises(IntegrationHold):
                store.synthetic_compare_swap(
                    replace(self.intent(),**changes),expected_main_sha=store.main_sha,
                )
        self.assertEqual(store.read(self.intent().target_local_ref),SHA0)

    def test_unknown_ref_and_untrusted_store_names_denied(self):
        from my_local_ai.gitops.local_integration import SyntheticIsolatedRefStore
        for ref in ("refs/heads/main","refs/remotes/origin/main",
                    "refs/heads/mla/isolated/xx.lock"):
            with self.assertRaises(IntegrationHold):
                SyntheticIsolatedRefStore({ref:SHA0},owner_original_sha=SHA1,main_sha="d"*40)
        store=self.store()
        with self.assertRaises(IntegrationHold):
            store.synthetic_compare_swap(
                replace(self.intent(),target_local_ref="refs/heads/mla/isolated/OTHER-1"),
                expected_main_sha=store.main_sha,
            )

    def test_altered_intent_cannot_write_in_memory(self):
        store=self.store()
        for changes in (
            {"proposed_candidate_sha":"f"*39},
            {"proposed_candidate_sha":SHA0},
            {"expected_old_sha":"f"*40},
        ):
            with self.assertRaises(IntegrationHold):
                store.synthetic_compare_swap(
                    replace(self.intent(),**changes),expected_main_sha=store.main_sha,
                )
        self.assertEqual(store.read(self.intent().target_local_ref),SHA0)


if __name__=="__main__":
    unittest.main()
