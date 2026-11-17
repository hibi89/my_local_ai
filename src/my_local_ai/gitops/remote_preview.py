"""Non-networking remote PR preview. Never sends data, pushes or opens PRs.

Even PUBLIC synthetic data requires specific owner GO and a future protected
publisher. V1 plan-wide LOCAL_PLAN HMAC CANNOT approve REMOTE_PR.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_TASK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_REF = re.compile(r"refs/heads/mla/review/[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


class RemotePreviewHold(ValueError):
    pass


@dataclass(frozen=True)
class RemoteProposal:
    repository: str
    task_id: str
    baseline_sha: str
    candidate_sha: str
    intended_ref: str
    classification: str


@dataclass(frozen=True)
class RemotePreview:
    repository: str
    task_id: str
    intended_ref: str
    source_sha: str
    candidate_sha: str
    status: str = "AWAIT_ACTION_SPECIFIC_OWNER_GO"
    authorized: bool = False
    network_enabled: bool = False
    push_allowed: bool = False
    pr_creation_allowed: bool = False
    customer_data_allowed: bool = False


def make_remote_preview(proposal: RemoteProposal, *,
                        exact_owner_grant_verified: bool = False) -> RemotePreview:
    """Only format sanitized proposal; no claim can enable network or PR."""
    if not isinstance(proposal,RemoteProposal):
        raise RemotePreviewHold("invalid proposal")
    if (not isinstance(proposal.repository,str) or not _REPO.fullmatch(proposal.repository)
        or any(segment in (".","..") or segment.endswith((".", ".lock")) for segment in proposal.repository.split("/"))
        or not isinstance(proposal.task_id,str) or not _TASK.fullmatch(proposal.task_id)
        or not isinstance(proposal.baseline_sha,str) or not _SHA.fullmatch(proposal.baseline_sha)
        or not isinstance(proposal.candidate_sha,str) or not _SHA.fullmatch(proposal.candidate_sha)
        or proposal.baseline_sha==proposal.candidate_sha
        or not isinstance(proposal.intended_ref,str) or not _REF.fullmatch(proposal.intended_ref)
        or proposal.intended_ref.endswith(("/main","/master"))
        or proposal.classification!="PUBLIC_SYNTHETIC_ONLY"):
        raise RemotePreviewHold("unsafe remote proposal")
    # This Boolean is NOT an action-bound protected signer proof. Even True is
    # not enough: REMOTE_PR is blocked until separate owner GO and P4 release.
    return RemotePreview(proposal.repository,proposal.task_id,proposal.intended_ref,
                         proposal.baseline_sha,proposal.candidate_sha)
