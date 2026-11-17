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
                     "hibi89//my_local_ai","../repo","hibi89/..","hibi89/.","hibi89/.git","hibi89/repo.lock","./repo"):
            with self.subTest(repo=repo),self.assertRaises(RemotePreviewHold):
                make_remote_preview(proposal(repository=repo))


from my_local_ai.gitops.remote_preview import (
    DraftTargetSnapshot, DraftPRPreview, preview_protected_draft,
)


def target(**changes):
    args=dict(
        repository="hibi89/my_local_ai",base_branch="main",
        expected_base_sha="d"*40,observed_base_sha="d"*40,
        protection_required=True,protection_observed=True,
        change_paths=("src/demo.py","tests/demo.py"),
    )
    args.update(changes)
    return DraftTargetSnapshot(**args)


class ProtectedDraftPreviewTests(unittest.TestCase):
    def test_read_only_draft_preview_redacts_files_and_never_posts(self):
        result=preview_protected_draft(proposal(),target())
        self.assertEqual(result.state,"READ_ONLY_DRAFT_PR_SIMULATION_OWNER_GO_REQUIRED")
        self.assertEqual(result.base_branch,"main")
        self.assertEqual(result.changed_file_count,2)
        self.assertFalse(result.remote_observed_live)
        self.assertFalse(result.draft_pr_created)
        self.assertFalse(result.remote_push_allowed)
        self.assertFalse(result.target_branch_modified)
        self.assertNotIn("src/demo.py",str(result))

    def test_user_go_boolean_cannot_create_remote_action(self):
        result=preview_protected_draft(
            proposal(),target(),exact_owner_grant_verified=True,
        )
        self.assertFalse(result.owner_action_grant_verified)
        self.assertFalse(result.draft_pr_created)

    def test_stale_branch_head_or_disabled_branch_protection_fails_closed(self):
        for changes in (
            {"observed_base_sha":"f"*40},
            {"expected_base_sha":"bad"},
            {"protection_required":False},
            {"protection_observed":False},
            {"base_branch":"../main"},
            {"base_branch":"feature//unsafe"},
            {"base_branch":"refs/heads/a.lock"},
            {"repository":"other/repo"},
            {"config_filters_unknown":True},
        ):
            with self.subTest(changes=changes),self.assertRaises(RemotePreviewHold):
                preview_protected_draft(proposal(),target(**changes))

    def test_untracked_ignored_and_untrusted_files_fails_closed(self):
        for changes in (
            {"ignored_or_untracked_paths":(".env",)},
            {"change_paths":()},
            {"change_paths":("src/demo.py","SRC/DEMO.PY")},
            {"change_paths":(".git/config",)},
            {"change_paths":("src/file:ads",)},
            {"change_paths":("src/../private.txt",)},
            {"change_paths":("src/*.py",)},
        ):
            with self.subTest(changes=changes),self.assertRaises(RemotePreviewHold):
                preview_protected_draft(proposal(),target(**changes))

    def test_checked_source_does_not_make_local_ref_executable(self):
        result=preview_protected_draft(proposal(),target(base_branch="release/v1"))
        self.assertEqual(result.candidate_sha,CAND)
        self.assertEqual(result.source_sha,SRC)
        self.assertFalse(result.remote_push_allowed)


if __name__=="__main__":
    unittest.main()



class RemoteTaskAndPrivacyHardeningTests(unittest.TestCase):
    def test_review_ref_must_match_task_identity_even_for_synthetic_public(self):
        for changes in (
            {"intended_ref":"refs/heads/mla/review/OTHER-023"},
            {"task_id":"TASK-099"},
            {"exact_owner_grant_verified":"true"},
        ):
            with self.subTest(changes=changes),self.assertRaises(RemotePreviewHold):
                if "exact_owner_grant_verified" in changes:
                    make_remote_preview(
                        proposal(),exact_owner_grant_verified=changes["exact_owner_grant_verified"])
                else:
                    make_remote_preview(proposal(**changes))

    def test_sensitive_filenames_cannot_be_approved_as_public(self):
        for rel in (
            ".env", "src/.env.dev", "src/.aws/config", "src/.ssh/id_rsa",
            "src/secrets/api.json", "src/private/token.txt",
            "src/credentials.json", "src/id_ed25519",
            "certs/client.pem", "certs/client.KEY", "certs/wallet.p12",
        ):
            with self.subTest(rel=rel),self.assertRaises(RemotePreviewHold):
                preview_protected_draft(proposal(),target(change_paths=(rel,)))

    def test_ambiguous_base_and_base_equal_candidate_denied(self):
        for variant in (
            {"base_branch":"release/.hidden"},
            {"base_branch":"release/trailing."},
            {"expected_base_sha":CAND,"observed_base_sha":CAND},
        ):
            with self.subTest(variant=variant),self.assertRaises(RemotePreviewHold):
                preview_protected_draft(proposal(),target(**variant))

    def test_no_remote_boolean_can_mint_real_remote_approval(self):
        out=preview_protected_draft(
            proposal(),target(),exact_owner_grant_verified=True)
        self.assertFalse(out.owner_action_grant_verified)
        self.assertFalse(out.remote_observed_live)
        self.assertFalse(out.draft_pr_created)
