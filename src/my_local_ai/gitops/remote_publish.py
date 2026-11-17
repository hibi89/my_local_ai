"""Remote publishing consent gate. No push/PR/network code in P1.

A plan-level LOCAL_PLAN consent must never be reused for REMOTE_PR.
Only a future action-bound owner signer, protected Git ref readback, F18
review and explicit release gate may authorize actual publication.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

from my_local_ai.contracts.approval import OwnerGrant,authorize_claim
from my_local_ai.gitops.remote_preview import RemotePreview

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"refs/heads/mla/review/[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_BASE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")


@dataclass(frozen=True)
class PublishGate:
    status: str
    target_repo: str
    candidate_sha: str
    owner_go_verified: bool = False
    network_enabled: bool = False
    publish_allowed: bool = False
    may_open_pr: bool = False
    may_change_main: bool = False


def inspect_remote_publish(
    preview: RemotePreview, *,
    owner_grant: OwnerGrant | None = None,
    trusted_hmac_key: bytes | None = None,
    live_consent_check=None,
    now_seconds: int = 0,
    expected_plan_sha: str = "",
    expected_source_sha: str = "",
) -> PublishGate:
    """Data-only inspection. Does not send anything or authorize an action."""
    if (not isinstance(preview,RemotePreview)
        or preview.status!="AWAIT_ACTION_SPECIFIC_OWNER_GO"
        or preview.authorized or preview.network_enabled
        or preview.push_allowed or preview.pr_creation_allowed
        or not isinstance(preview.candidate_sha,str)
        or not _SHA.fullmatch(preview.candidate_sha)):
        raise ValueError("unrecognized remote proposal")
    # This intentionally fails because V1 scopes are LOCAL_PLAN-only; the
    # separately protected action-bound REMOTE_PR signer is not implemented.
    claim_is_valid=authorize_claim(
        owner_grant,trusted_hmac_key=trusted_hmac_key,
        expected_plan_sha=expected_plan_sha,expected_source_sha=expected_source_sha,
        required_scope="REMOTE_PR",now_seconds=now_seconds,
        trusted_live_consent_check=live_consent_check,
    )
    if claim_is_valid:
        # Never allow a high-risk publish through a scope-only HMAC grant.
        raise ValueError("unexpected remote privilege escalation")
    return PublishGate(
        "HOLD_ACTION_SPECIFIC_GO_AND_F18",
        preview.repository,preview.candidate_sha,
    )


# Future one-shot remote action fingerprint: a digest is NOT an owner signer,
# nor a license/egress permit. Actual GitHub API calls remain absent.
from hashlib import sha256 as _sha256
import json as _json
from my_local_ai.gitops.remote_preview import DraftPRPreview


@dataclass(frozen=True)
class DraftActionIntent:
    repository: str
    base_branch: str
    base_sha: str
    candidate_sha: str
    action_sha256: str
    state: str = "REMOTE_DRAFT_ACTION_OWNER_GO_HOLD"
    owner_go_verified: bool = False
    network_enabled: bool = False
    may_create_pr: bool = False
    may_merge: bool = False


def prepare_draft_action_intent(draft: DraftPRPreview) -> DraftActionIntent:
    if (not isinstance(draft, DraftPRPreview)
        or draft.state != "READ_ONLY_DRAFT_PR_SIMULATION_OWNER_GO_REQUIRED"
        or draft.owner_action_grant_verified or draft.remote_observed_live
        or draft.draft_pr_created or draft.remote_push_allowed
        or draft.target_branch_modified
        or type(draft.changed_file_count) is not int
        or not 1 <= draft.changed_file_count <= 16
        or not isinstance(draft.repository, str)
        or not _REPO.fullmatch(draft.repository)
        or not isinstance(draft.base_branch, str)
        or not _BASE.fullmatch(draft.base_branch)
        or ".." in draft.base_branch or "//" in draft.base_branch
        or any(part.startswith(".") or part.endswith(".") for part in draft.base_branch.split("/"))
        or not isinstance(draft.target_local_ref, str)
        or not _REF.fullmatch(draft.target_local_ref)
        or not isinstance(draft.source_sha, str)
        or not _SHA.fullmatch(draft.source_sha)
        or not isinstance(draft.change_paths_sha256, str)
        or not _DIGEST.fullmatch(draft.change_paths_sha256)
        or not isinstance(draft.expected_base_sha, str)
        or not _SHA.fullmatch(draft.expected_base_sha)
        or not isinstance(draft.candidate_sha, str)
        or not _SHA.fullmatch(draft.candidate_sha)
        or draft.candidate_sha in (draft.source_sha, draft.expected_base_sha)):
        raise ValueError("untrusted remote action preflight")
    payload=_json.dumps({
        "operation":"DRAFT_PR_ONLY","repository":draft.repository,
        "base":draft.base_branch,"base_sha":draft.expected_base_sha,
        "source_sha":draft.source_sha,"candidate_sha":draft.candidate_sha,
        "target_local_ref":draft.target_local_ref,
        "changed_file_count":draft.changed_file_count,
        "change_paths_sha256":draft.change_paths_sha256,
    },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    digest=_sha256(b"mla-draft-pr/v1|"+payload).hexdigest()
    return DraftActionIntent(
        draft.repository,draft.base_branch,
        draft.expected_base_sha,draft.candidate_sha,digest,
    )


# SWU-029: narrowly scoped one-shot draft PR source port for an independently
# protected future publisher. V1 refuses REMOTE_PR at authorize_claim; neither
# this function nor a prepared intent is approval to upload even public code.
from urllib.parse import quote as _url_quote


class DraftPublishHold(ValueError):
    """Remote publishing remains HOLD on any stale grant or readback."""


@dataclass(frozen=True)
class DraftPublishReceipt:
    repository: str
    candidate_sha: str
    review_ref: str
    draft_pr_number: int
    draft_pr_url: str
    state: str = "REMOTE_DRAFT_CREATED_AWAIT_INDEPENDENT_VERIFICATION"
    may_merge: bool = False
    may_change_main: bool = False
    may_publish_further: bool = False
    release_approved: bool = False


def publish_action_bound_draft_pr(
    draft: DraftPRPreview, intent: DraftActionIntent, *,
    plan_sha256: str, owner_grant: OwnerGrant | None,
    trusted_hmac_key: bytes | None, trusted_live_consent_check,
    now_seconds: int, protected_f18_acceptance,
    protected_remote_readback, protected_push_new_ref,
    protected_create_draft_pr,
) -> DraftPublishReceipt:
    """One protected PUBLIC_SYNTHETIC_ONLY draft PR; never merges or force-pushes.

    No callback may run until the exact REMOTE_PR action consent validates.
    Today's V1 signer always rejects REMOTE_PR, so calling this function
    with guest-supplied functions cannot cause network activity. Future
    High+owner approval must also establish independently protected F18
    acceptance, content classification, remote-ref pin and one-shot replay.
    """
    if (not isinstance(draft, DraftPRPreview)
        or not isinstance(intent, DraftActionIntent)
        or intent != prepare_draft_action_intent(draft)
        or intent.state != "REMOTE_DRAFT_ACTION_OWNER_GO_HOLD"
        or intent.owner_go_verified is not False
        or intent.network_enabled is not False
        or intent.may_create_pr is not False
        or intent.may_merge is not False
        or not isinstance(plan_sha256, str)
        or not _DIGEST.fullmatch(plan_sha256)
        or type(now_seconds) is not int or now_seconds <= 0
        or not all(callable(cb) for cb in (
            protected_f18_acceptance, protected_remote_readback,
            protected_push_new_ref, protected_create_draft_pr,
        ))):
        raise DraftPublishHold("INVALID_REMOTE_INTENT")
    if not authorize_claim(
        owner_grant, trusted_hmac_key=trusted_hmac_key,
        expected_plan_sha=plan_sha256,
        expected_source_sha=draft.source_sha,
        required_scope="REMOTE_PR", now_seconds=now_seconds,
        trusted_live_consent_check=trusted_live_consent_check,
    ):
        raise DraftPublishHold("REMOTE_ACTION_OWNER_GO_REQUIRED")

    # A future protected publisher supplies these sealed callbacks (not an
    # agent-provided HTTP client) and validates the action nonce is unspent.
    # All callbacks must revalidate exactly the same repository and action.
    ref = draft.target_local_ref
    if (not _REF.fullmatch(ref)
        or draft.candidate_sha in (draft.source_sha,draft.expected_base_sha)
        or draft.repository != intent.repository
        or draft.base_branch != intent.base_branch
        or draft.expected_base_sha != intent.base_sha):
        raise DraftPublishHold("INVALID_REMOTE_INTENT")
    try:
        valid_f18 = protected_f18_acceptance(
            plan_sha256, draft.source_sha, draft.candidate_sha,
            intent.action_sha256,
        )
        snapshot = protected_remote_readback(
            intent.repository, intent.base_branch, ref,
        )
    except Exception:
        raise DraftPublishHold("PROTECTED_READBACK_FAILED") from None
    if valid_f18 is not True or type(snapshot) is not dict:
        raise DraftPublishHold("F18_OR_REMOTE_TARGET_HOLD")
    if (set(snapshot) != {
            "base_sha","branch_sha","base_protected",
            "public_synthetic_attested","action_unspent",
        } or snapshot["base_sha"] != intent.base_sha
        or snapshot["branch_sha"] is not None
        or snapshot["base_protected"] is not True
        or snapshot["public_synthetic_attested"] is not True
        or snapshot["action_unspent"] is not True):
        raise DraftPublishHold("F18_OR_REMOTE_TARGET_HOLD")
    # Never --force or reuse an existing branch. If push partially succeeds
    # and PR creation fails, leave the branch for owner-side reconciliation.
    try:
        pushed = protected_push_new_ref(
            intent.repository, draft.candidate_sha, ref,
            expected_remote_old_sha=None, force=False,
        )
        if pushed is not True:
            raise DraftPublishHold("REMOTE_PUSH_FAILED")
        fresh = protected_remote_readback(
            intent.repository, intent.base_branch, ref,
        )
        if (type(fresh) is not dict
            or fresh.get("base_sha") != intent.base_sha
            or fresh.get("branch_sha") != draft.candidate_sha
            or fresh.get("base_protected") is not True):
            raise DraftPublishHold("REMOTE_PARTIAL_RECONCILIATION_REQUIRED")
        response = protected_create_draft_pr(
            intent.repository, base_branch=intent.base_branch,
            head_ref=ref, title="My Local AI isolated review",
            body="Owner-authorized draft; no automatic merge or release.",
            draft=True,
        )
    except DraftPublishHold:
        raise
    except Exception:
        raise DraftPublishHold("REMOTE_PARTIAL_RECONCILIATION_REQUIRED") from None
    if (type(response) is not dict or set(response) != {"number","url","draft"}
        or type(response["number"]) is not int
        or response["number"] <= 0 or response["draft"] is not True
        or response["url"] != (
            "https://github.com/" + intent.repository + "/pull/" +
            str(response["number"])
        )):
        raise DraftPublishHold("REMOTE_PARTIAL_RECONCILIATION_REQUIRED")
    return DraftPublishReceipt(
        intent.repository, draft.candidate_sha, ref,
        response["number"], response["url"],
    )
