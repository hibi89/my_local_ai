"""Non-networking remote PR preview. Never sends data, pushes or opens PRs.

Even PUBLIC synthetic data requires specific owner GO and a future protected
publisher. V1 plan-wide LOCAL_PLAN HMAC CANNOT approve REMOTE_PR.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
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
        or proposal.intended_ref != "refs/heads/mla/review/" + proposal.task_id
        or proposal.intended_ref.endswith(("/main","/master"))
        or proposal.classification!="PUBLIC_SYNTHETIC_ONLY"
        or type(exact_owner_grant_verified) is not bool):
        raise RemotePreviewHold("unsafe remote proposal")
    # This Boolean is NOT an action-bound protected signer proof. Even True is
    # not enough: REMOTE_PR is blocked until separate owner GO and P4 release.
    return RemotePreview(proposal.repository,proposal.task_id,proposal.intended_ref,
                         proposal.baseline_sha,proposal.candidate_sha)


# Read-only policy comparison for a future draft PR. This code never contacts
# GitHub: branch protection and head SHA must later be re-fetched by a
# protected owner caller immediately before an explicitly approved operation.
from my_local_ai.contracts.task import safe_path as _safe_path

_BASE_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")
_SENSITIVE_PARTS = frozenset({"secrets", "credentials", "private", "id_rsa", "id_ed25519"})
_SENSITIVE_EXTENSIONS = (".pem", ".key", ".p12", ".pfx", ".kdbx")


def _public_synthetic_file(relative: str) -> bool:
    """Never claim a private path is safe for future remote disclosure."""
    for segment in relative.split("/"):
        lower = segment.casefold()
        if (not lower or lower.startswith(".") or lower in _SENSITIVE_PARTS
            or lower.endswith(_SENSITIVE_EXTENSIONS)
            or lower.startswith((".env", ".npmrc", ".pypirc",
                                 "credentials.", "credential.", "secrets.",
                                 "secret.", "token.", "api_key.", "private_key."))):
            return False
    return True


@dataclass(frozen=True)
class DraftTargetSnapshot:
    repository: str
    base_branch: str
    expected_base_sha: str
    observed_base_sha: str
    protection_required: bool
    protection_observed: bool
    change_paths: tuple[str, ...]
    ignored_or_untracked_paths: tuple[str, ...] = ()
    config_filters_unknown: bool = False


@dataclass(frozen=True)
class DraftPRPreview:
    repository: str
    base_branch: str
    expected_base_sha: str
    source_sha: str
    candidate_sha: str
    changed_file_count: int
    target_local_ref: str
    state: str = "READ_ONLY_DRAFT_PR_SIMULATION_OWNER_GO_REQUIRED"
    remote_observed_live: bool = False
    owner_action_grant_verified: bool = False
    draft_pr_created: bool = False
    remote_push_allowed: bool = False
    target_branch_modified: bool = False
    change_paths_sha256: str = ""  # metadata claim, not owner proof


def preview_protected_draft(
    proposal: RemoteProposal, snapshot: DraftTargetSnapshot, *,
    exact_owner_grant_verified: bool = False,
) -> DraftPRPreview:
    """Validate metadata only and redact sensitive filenames from output."""
    reviewed = make_remote_preview(
        proposal, exact_owner_grant_verified=exact_owner_grant_verified,
    )
    if not isinstance(snapshot, DraftTargetSnapshot):
        raise RemotePreviewHold("target policy missing")
    if (not isinstance(snapshot.repository, str)
        or snapshot.repository != reviewed.repository
        or not isinstance(snapshot.base_branch, str)
        or not _BASE_BRANCH.fullmatch(snapshot.base_branch)
        or ".." in snapshot.base_branch
        or "//" in snapshot.base_branch
        or any(part.startswith(".") or part.endswith(".") for part in snapshot.base_branch.split("/"))
        or snapshot.base_branch.endswith((".lock", ".", "/"))
        or not isinstance(snapshot.expected_base_sha, str)
        or not _SHA.fullmatch(snapshot.expected_base_sha)
        or snapshot.observed_base_sha != snapshot.expected_base_sha
        or snapshot.expected_base_sha == reviewed.candidate_sha
        or snapshot.protection_required is not True
        or snapshot.protection_observed is not True
        or snapshot.config_filters_unknown is not False):
        raise RemotePreviewHold("protected draft target is not pinned")
    paths = snapshot.change_paths
    if (not isinstance(paths, tuple) or not 1 <= len(paths) <= 16
        or not isinstance(snapshot.ignored_or_untracked_paths, tuple)
        or snapshot.ignored_or_untracked_paths):
        raise RemotePreviewHold("unsafe draft change inventory")
    seen: set[str] = set()
    for p in paths:
        try:
            checked = _safe_path(p)
        except ValueError:
            raise RemotePreviewHold("unsafe draft filename") from None
        if checked.casefold() in seen:
            raise RemotePreviewHold("duplicate draft change")
        if not _public_synthetic_file(checked):
            raise RemotePreviewHold("sensitive or hidden source cannot be considered public")
        seen.add(checked.casefold())
    # Important: this metadata is a caller-provided CLAIM, not a live
    # GitHub protection readback or a data classification attestation.
    # A file count is insufficient to bind a specific future draft action.
    manifest = json.dumps(sorted(paths, key=str.casefold), ensure_ascii=True,
                          separators=(",", ":")).encode("ascii")
    paths_digest = hashlib.sha256(b"mla-draft-paths/v1|" + manifest).hexdigest()
    return DraftPRPreview(
        reviewed.repository, snapshot.base_branch,
        snapshot.expected_base_sha, reviewed.source_sha,
        reviewed.candidate_sha, len(paths), reviewed.intended_ref,
        change_paths_sha256=paths_digest,
    )
