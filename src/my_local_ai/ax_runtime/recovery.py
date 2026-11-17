"""P1 pure recovery policy: one repair proposal, never an execution command.

A protected controller/SQLite lease store must independently establish these
inputs before any future execution. Guest receipts, old epochs and state labels
are not trusted verification. There is no shell, DB write, model call or Git ref.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_EVENTS = frozenset({"REVIEW_FAILED", "CODER_INTERRUPTED", "REVIEW_PENDING", "REVIEW_PASSED_CLAIM"})


@dataclass(frozen=True)
class RecoveryCheckpoint:
    run_id: str
    task_id: str
    plan_sha: str
    baseline_sha: str
    lease_epoch: int
    attempts_used: int
    candidate_sha: str | None
    state: str

    def __post_init__(self):
        if (not isinstance(self.run_id, str) or not _NAME.fullmatch(self.run_id)
            or not isinstance(self.task_id, str) or not _NAME.fullmatch(self.task_id)
            or not isinstance(self.plan_sha, str) or not _SHA64.fullmatch(self.plan_sha)
            or not isinstance(self.baseline_sha, str) or not _SHA40.fullmatch(self.baseline_sha)
            or type(self.lease_epoch) is not int or self.lease_epoch <= 0
            or type(self.attempts_used) is not int or not 0 <= self.attempts_used <= 2
            or (self.candidate_sha is not None
                and (not isinstance(self.candidate_sha, str)
                     or not _SHA40.fullmatch(self.candidate_sha)))
            or self.state not in {"CODING", "REVIEW_PENDING", "REPAIR_ONCE", "INTERRUPTED", "HOLD"}):
            raise ValueError("invalid recovery checkpoint")


@dataclass(frozen=True)
class RecoveryProposal:
    state: str
    reason: str
    next_attempt: int | None
    minimum_next_lease_epoch: int
    pinned_plan_sha: str
    pinned_baseline_sha: str
    requires_new_owner_grant: bool
    runnable: bool = False
    verified: bool = False


def propose_recovery(
    checkpoint: RecoveryCheckpoint, *, event: str,
    expected_plan_sha: str, expected_baseline_sha: str,
    observed_lease_epoch: int, independently_accepted_candidate: bool = False,
) -> RecoveryProposal:
    """Does not accept an 'independently accepted' boolean as F18 evidence.

    Any apparent positive PASS must go to the separate trusted reviewer and
    local integration boundary, which this policy intentionally cannot invoke.
    """
    if (not isinstance(checkpoint, RecoveryCheckpoint)
        or not isinstance(event, str) or event not in _EVENTS
        or expected_plan_sha != checkpoint.plan_sha
        or expected_baseline_sha != checkpoint.baseline_sha
        or type(observed_lease_epoch) is not int
        or observed_lease_epoch != checkpoint.lease_epoch
        or independently_accepted_candidate is not False):
        raise ValueError("untrusted or stale recovery evidence")
    floor = checkpoint.lease_epoch + 1
    if event == "REVIEW_PASSED_CLAIM":
        return RecoveryProposal("HOLD", "PASS_CLAIM_NEEDS_INDEPENDENT_F18", None, floor,
                                checkpoint.plan_sha, checkpoint.baseline_sha, True)
    if event == "REVIEW_PENDING":
        return RecoveryProposal("HOLD", "AWAIT_INDEPENDENT_REVIEW", None, floor,
                                checkpoint.plan_sha, checkpoint.baseline_sha, False)
    if event == "CODER_INTERRUPTED":
        return RecoveryProposal("INTERRUPTED", "LEASE_INVALIDATE_AND_RECHECK", None, floor,
                                checkpoint.plan_sha, checkpoint.baseline_sha, True)
    # A failed independent review can propose at most one repair. The
    # controller must issue a fresh lease/owner grant and re-attest source.
    if checkpoint.state not in {"REVIEW_PENDING", "REPAIR_ONCE"}:
        return RecoveryProposal("HOLD", "MISSING_REVIEW_BOUNDARY", None, floor,
                                checkpoint.plan_sha, checkpoint.baseline_sha, True)
    if checkpoint.attempts_used != 1:
        return RecoveryProposal("HOLD", "REPAIR_EXHAUSTED_OR_INVALID", None, floor,
                                checkpoint.plan_sha, checkpoint.baseline_sha, True)
    return RecoveryProposal("REPAIR_ONCE", "SUGGEST_ONE_REPAIR_ONLY", 2, floor,
                            checkpoint.plan_sha, checkpoint.baseline_sha, True)
