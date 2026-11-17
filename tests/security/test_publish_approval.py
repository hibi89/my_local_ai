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


if __name__=="__main__":
    unittest.main()
