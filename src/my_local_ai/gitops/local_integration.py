"""Local-only Git CAS integration contract. No git invocation or ref mutation.

CRITICAL: an HMAC-valid guest receipt is NOT independent F18 evidence.
This module can prepare an isolated-ref intent only; trusted owner controller
must independently verify Windows reviewer, exact file inventory, protected
consent, OS principal, hook/filter safety, and perform the actual ref CAS.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from my_local_ai.review.receipt_guard import ReceiptInspection

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_TASK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_ISOLATED = re.compile(r"refs/heads/mla/isolated/[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


class IntegrationHold(ValueError):
    def __init__(self, reason: str = "F18_NOT_INDEPENDENT"):
        self.code = reason if reason in {
            "F18_NOT_INDEPENDENT", "STALE_ORIGINAL", "BAD_REF",
            "UNTRUSTED_REVIEW", "SHA_MISMATCH", "MISSING_OWNER_GO",
        } else "F18_NOT_INDEPENDENT"
        super().__init__(self.code)


@dataclass(frozen=True)
class RefSnapshot:
    """Expected values from independently protected Git readback."""
    target_local_ref: str
    expected_old_sha: str
    actual_old_sha: str
    owner_original_sha: str
    original_readback_sha: str


@dataclass(frozen=True)
class LocalCASIntent:
    target_local_ref: str
    expected_old_sha: str
    proposed_candidate_sha: str
    owner_original_sha: str
    task_id: str
    state: str = "HOLD_PENDING_INDEPENDENT_F18_AND_OWNER_GO"
    executable: bool = False
    may_write_ref: bool = False
    may_write_original: bool = False
    may_push_remote: bool = False


def plan_isolated_local_cas(
    *, task_id: str, candidate_sha: str,
    snapshot: RefSnapshot, inspection: ReceiptInspection | None,
    trusted_owner_grant_present: bool = False,
) -> LocalCASIntent:
    """Guard the *shape* of a future CAS. Never executes Git/changes disk.

    An argument flag cannot certify owner GO. A syntactically valid proposal
    remains HOLD even if it includes a matching HMAC inspection.
    """
    if (not isinstance(task_id,str) or not _TASK.fullmatch(task_id)
        or not isinstance(candidate_sha,str) or not _SHA.fullmatch(candidate_sha)
        or not isinstance(snapshot,RefSnapshot)):
        raise IntegrationHold("SHA_MISMATCH")
    if (not isinstance(snapshot.target_local_ref,str)
        or not _ISOLATED.fullmatch(snapshot.target_local_ref)
        or snapshot.target_local_ref.endswith(("/main","/master"))
        or ".." in snapshot.target_local_ref):
        raise IntegrationHold("BAD_REF")
    if any(not isinstance(value,str) or not _SHA.fullmatch(value) for value in (
        snapshot.expected_old_sha, snapshot.actual_old_sha,
        snapshot.owner_original_sha, snapshot.original_readback_sha,
    )):
        raise IntegrationHold("SHA_MISMATCH")
    if snapshot.owner_original_sha != snapshot.original_readback_sha:
        raise IntegrationHold("STALE_ORIGINAL")
    if snapshot.expected_old_sha != snapshot.actual_old_sha:
        raise IntegrationHold("SHA_MISMATCH")
    if snapshot.actual_old_sha == candidate_sha or snapshot.owner_original_sha == candidate_sha:
        raise IntegrationHold("SHA_MISMATCH")
    if inspection is None or not isinstance(inspection,ReceiptInspection):
        raise IntegrationHold("UNTRUSTED_REVIEW")
    if (inspection.task_id != task_id or inspection.candidate_sha != candidate_sha
        or inspection.signature_matches is not True):
        raise IntegrationHold("UNTRUSTED_REVIEW")
    # A valid MAC is not OS principal separation, and a caller can forge an
    # inspection dataclass. Even a True flag cannot authorize this method.
    if inspection.independent_os_review_proven is not True or inspection.may_promote_git_ref is not True:
        raise IntegrationHold("F18_NOT_INDEPENDENT")
    if trusted_owner_grant_present is not True:
        raise IntegrationHold("MISSING_OWNER_GO")
    # Still NOT executable: only a separately trusted controller can issue a
    # protected ref transaction with a fresh owner grant and correct lease.
    return LocalCASIntent(
        snapshot.target_local_ref, snapshot.expected_old_sha,
        candidate_sha, snapshot.owner_original_sha, task_id,
    )
