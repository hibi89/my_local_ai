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
