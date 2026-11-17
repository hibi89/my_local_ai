"""Remote GO refusal: no GitHub API, no branch changes or network."""
from dataclasses import replace
import hashlib
import hmac
import unittest

from my_local_ai.contracts.approval import OwnerGrant
from my_local_ai.gitops.remote_publish import inspect_remote_publish
from my_local_ai.gitops.remote_preview import RemoteProposal,make_remote_preview

PLAN="a"*64
SOURCE="b"*40
CANDIDATE="c"*40
KEY=b"test-not-production-owner-key-32bytes-123456"


def preview():
    return make_remote_preview(RemoteProposal(
        repository="hibi89/my_local_ai",task_id="TASK-024",
        baseline_sha=SOURCE,candidate_sha=CANDIDATE,
        intended_ref="refs/heads/mla/review/TASK-024",
        classification="PUBLIC_SYNTHETIC_ONLY",
    ))


class PublishConsentBoundaryTests(unittest.TestCase):
    def test_default_go_is_hold_and_no_pr_ever(self):
        r=inspect_remote_publish(preview())
        self.assertEqual(r.status,"HOLD_ACTION_SPECIFIC_GO_AND_F18")
        self.assertFalse(r.publish_allowed)
        self.assertFalse(r.network_enabled)
        self.assertFalse(r.may_open_pr)
        self.assertFalse(r.may_change_main)

    def test_plan_scope_signature_never_authorizes_remote(self):
        unsigned=OwnerGrant("grant0001",PLAN,SOURCE,"LOCAL_PLAN",100,300,
                            "nonce0001","0"*64)
        signature=hmac.new(KEY,b"mla-owner-go/v1|"+unsigned.payload(),hashlib.sha256).hexdigest()
        signed=replace(unsigned,signature=signature)
        out=inspect_remote_publish(
            preview(),owner_grant=signed,trusted_hmac_key=KEY,
            live_consent_check=lambda *_:True,now_seconds=150,
            expected_plan_sha=PLAN,expected_source_sha=SOURCE,
        )
        self.assertFalse(out.publish_allowed)

    def test_remote_scope_signature_alone_still_never_authorizes(self):
        unsigned=OwnerGrant("grant0001",PLAN,SOURCE,"REMOTE_PR",100,300,
                            "nonce0001","0"*64)
        signature=hmac.new(KEY,b"mla-owner-go/v1|"+unsigned.payload(),hashlib.sha256).hexdigest()
        signed=replace(unsigned,signature=signature)
        out=inspect_remote_publish(
            preview(),owner_grant=signed,trusted_hmac_key=KEY,
            live_consent_check=lambda *_:True,now_seconds=150,
            expected_plan_sha=PLAN,expected_source_sha=SOURCE,
        )
        self.assertFalse(out.publish_allowed)
        self.assertFalse(out.owner_go_verified)

    def test_fake_preview_claimed_network_is_rejected(self):
        unsafe=replace(preview(),authorized=True,network_enabled=True,push_allowed=True)
        with self.assertRaises(ValueError):
            inspect_remote_publish(unsafe)

    def test_every_field_is_non_privileged_even_with_fake_approval(self):
        out=inspect_remote_publish(preview(),owner_grant=None)
        self.assertFalse(out.may_open_pr)
        self.assertFalse(out.may_change_main)
        self.assertFalse(out.owner_go_verified)


from my_local_ai.gitops.remote_preview import DraftTargetSnapshot,preview_protected_draft
from my_local_ai.gitops.remote_publish import prepare_draft_action_intent


def draft_fixture(**changes):
    props=dict(
        repository="hibi89/my_local_ai",base_branch="main",
        expected_base_sha="d"*40,observed_base_sha="d"*40,
        protection_required=True,protection_observed=True,
        change_paths=("src/synthetic.py",),
    )
    props.update(changes)
    return preview_protected_draft(
        RemoteProposal(
            repository="hibi89/my_local_ai",task_id="TASK-024",
            baseline_sha=SOURCE,candidate_sha=CANDIDATE,
            intended_ref="refs/heads/mla/review/TASK-024",
            classification="PUBLIC_SYNTHETIC_ONLY",
        ),DraftTargetSnapshot(**props),
    )


class DraftActionHashTests(unittest.TestCase):
    def test_action_sha_binds_base_sha_and_cannot_create_pr(self):
        first=prepare_draft_action_intent(draft_fixture())
        other=prepare_draft_action_intent(
            draft_fixture(expected_base_sha="e"*40,observed_base_sha="e"*40)
        )
        self.assertNotEqual(first.action_sha256,other.action_sha256)
        self.assertFalse(first.network_enabled)
        self.assertFalse(first.owner_go_verified)
        self.assertFalse(first.may_create_pr)
        self.assertFalse(first.may_merge)

    def test_action_fingerprint_binds_paths_source_and_review_ref(self):
        baseline=prepare_draft_action_intent(draft_fixture()).action_sha256
        changed_paths=prepare_draft_action_intent(
            draft_fixture(change_paths=("src/another.py",))
        ).action_sha256
        self.assertNotEqual(baseline,changed_paths)
        self.assertNotEqual(baseline,prepare_draft_action_intent(
            replace(draft_fixture(),source_sha="f"*40)
        ).action_sha256)
        self.assertNotEqual(baseline,prepare_draft_action_intent(
            replace(draft_fixture(),target_local_ref="refs/heads/mla/review/DIFF-025")
        ).action_sha256)

    def test_forged_remote_success_and_invalid_candidates_fail_shut(self):
        for changes in (
            {"draft_pr_created":True},
            {"owner_action_grant_verified":True},
            {"remote_push_allowed":True},
            {"candidate_sha":"bad"},
            {"changed_file_count":0},
            {"change_paths_sha256":"bad"},
            {"target_local_ref":"refs/heads/main"},
            {"source_sha":"bad"},
            {"base_branch":"../main"},
        ):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                prepare_draft_action_intent(replace(draft_fixture(),**changes))


if __name__=="__main__":
    unittest.main()
