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
    if checkpoint.state != "REVIEW_PENDING" or checkpoint.candidate_sha is None:
        return RecoveryProposal("HOLD", "MISSING_REVIEW_BOUNDARY", None, floor,
                                checkpoint.plan_sha, checkpoint.baseline_sha, True)
    if checkpoint.attempts_used != 1:
        return RecoveryProposal("HOLD", "REPAIR_EXHAUSTED_OR_INVALID", None, floor,
                                checkpoint.plan_sha, checkpoint.baseline_sha, True)
    return RecoveryProposal("REPAIR_ONCE", "SUGGEST_ONE_REPAIR_ONLY", 2, floor,
                            checkpoint.plan_sha, checkpoint.baseline_sha, True)


# A second attempt must include a *different* bounded corrective strategy,
# not a blind retry of the same failed prompt, tool or command. This is still a
# scheduling request only: owner consent, a new fenced lease, OS isolation,
# and F18 verification must occur in other protected components.
from hashlib import sha256 as _sha256

_ALLOWED_FAILURES=frozenset({
    "SYNTAX_ERROR", "UNIT_FAILURE", "SECURITY_FAILURE",
    "CONTRACT_FAILURE", "SANDBOX_TIMEOUT",
})
_ALLOWED_FIXES=frozenset({
    "LIMITED_SYNTAX_REPAIR", "ISOLATED_UNIT_FIX",
    "NARROW_PERMISSION_FIX", "CONTRACT_SCOPE_CORRECTION",
    "REDUCE_BATCH_MEMORY",
})
# A different label alone is not a plausible improvement. Intent is still a
# proposal, never evidence that the changed strategy actually fixed anything.
_FAILURE_STRATEGIES = {
    "SYNTAX_ERROR": frozenset({"LIMITED_SYNTAX_REPAIR"}),
    "UNIT_FAILURE": frozenset({"ISOLATED_UNIT_FIX", "LIMITED_SYNTAX_REPAIR"}),
    "SECURITY_FAILURE": frozenset({"NARROW_PERMISSION_FIX", "CONTRACT_SCOPE_CORRECTION"}),
    "CONTRACT_FAILURE": frozenset({"CONTRACT_SCOPE_CORRECTION", "ISOLATED_UNIT_FIX"}),
    "SANDBOX_TIMEOUT": frozenset({"REDUCE_BATCH_MEMORY"}),
}


@dataclass(frozen=True)
class RepairIntent:
    task_id: str
    run_id: str
    source_sha: str
    plan_sha256: str
    previous_candidate_sha: str
    error_fingerprint_sha256: str
    new_strategy: str
    expected_previous_epoch: int
    minimum_next_epoch: int
    attempt_number: int = 2
    state: str = "IMPROVED_REPAIR_PROPOSAL_OWNER_GO_REQUIRED"
    auto_retry: bool = False
    may_run_on_host: bool = False
    may_mark_verified: bool = False


def plan_improved_repair(
    checkpoint: RecoveryCheckpoint, *,
    failed_check: str, failure_fingerprint_sha256: str,
    previous_strategy: str, proposed_strategy: str,
    observed_epoch: int, plan_sha256: str, source_sha: str,
) -> RepairIntent:
    """Reject same-method retries and untrusted/stale failure summaries."""
    if (not isinstance(checkpoint,RecoveryCheckpoint)
        or failed_check not in _ALLOWED_FAILURES
        or not isinstance(failure_fingerprint_sha256,str)
        or not _SHA64.fullmatch(failure_fingerprint_sha256)
        or previous_strategy not in _ALLOWED_FIXES
        or proposed_strategy not in _ALLOWED_FIXES
        or proposed_strategy == previous_strategy
        or proposed_strategy not in _FAILURE_STRATEGIES.get(failed_check, ())
        or checkpoint.candidate_sha is None):
        raise ValueError("invalid or unimproved repair evidence")
    proposal=propose_recovery(
        checkpoint,event="REVIEW_FAILED",
        expected_plan_sha=plan_sha256,
        expected_baseline_sha=source_sha,
        observed_lease_epoch=observed_epoch,
    )
    if proposal.state!="REPAIR_ONCE" or proposal.next_attempt!=2:
        raise ValueError("repair exhausted or untrusted")
    return RepairIntent(
        checkpoint.task_id,checkpoint.run_id,checkpoint.baseline_sha,
        checkpoint.plan_sha,checkpoint.candidate_sha,
        failure_fingerprint_sha256,proposed_strategy,
        checkpoint.lease_epoch,proposal.minimum_next_lease_epoch,
    )
