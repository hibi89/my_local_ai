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
