"""No network/GitHub tool calls; redacted remote proposal only."""
from dataclasses import replace
import unittest

from my_local_ai.gitops.remote_preview import (
    RemoteProposal, RemotePreviewHold, make_remote_preview,
)

SRC="a"*40
CAND="b"*40


def proposal(**changes):
    args=dict(repository="hibi89/my_local_ai",task_id="TASK-023",
              baseline_sha=SRC,candidate_sha=CAND,
              intended_ref="refs/heads/mla/review/TASK-023",
              classification="PUBLIC_SYNTHETIC_ONLY")
    args.update(changes)
    return RemoteProposal(**args)


class RemotePreviewTests(unittest.TestCase):
    def test_preview_is_never_a_push_or_pr(self):
        result=make_remote_preview(proposal())
        self.assertEqual(result.status,"AWAIT_ACTION_SPECIFIC_OWNER_GO")
        self.assertFalse(result.network_enabled)
        self.assertFalse(result.push_allowed)
        self.assertFalse(result.pr_creation_allowed)
        self.assertFalse(result.customer_data_allowed)

    def test_fake_owner_boolean_cannot_unlock_remote(self):
        result=make_remote_preview(proposal(),exact_owner_grant_verified=True)
        self.assertFalse(result.authorized)
        self.assertFalse(result.network_enabled)

    def test_main_production_or_private_data_rejected(self):
        for change in (
            {"intended_ref":"refs/heads/main"},
            {"intended_ref":"refs/heads/mla/review/../main"},
            {"intended_ref":"refs/heads/mla/review/xx.lock"},
            {"intended_ref":"refs/remotes/origin/main"},
            {"classification":"PRIVATE_SOURCE"},
            {"classification":"CUSTOMER_DATA"},
            {"classification":"PRODUCTION"},
            {"candidate_sha":SRC},
            {"candidate_sha":"invalid"},
        ):
            with self.subTest(change=change),self.assertRaises(RemotePreviewHold):
                make_remote_preview(proposal(**change))

    def test_untrusted_ref_and_repo_schema_rejected(self):
        for repo in ("https://github.com/hibi89/my_local_ai",
                     "hibi89/my_local_ai;curl evil",
                     "hibi89//my_local_ai","../repo"):
            with self.subTest(repo=repo),self.assertRaises(RemotePreviewHold):
                make_remote_preview(proposal(repository=repo))


if __name__=="__main__":
    unittest.main()
