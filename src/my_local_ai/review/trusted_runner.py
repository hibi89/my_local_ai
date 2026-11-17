"""F18 isolated review request contract. Never executes untrusted code.

A real separated reviewer/runtime must be implemented and tested under the
owner Windows OS boundary. This file cannot mint trusted receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


@dataclass(frozen=True)
class ReviewRequest:
    task_id: str
    run_id: str
    candidate_sha: str
    source_sha: str
    plan_sha256: str
    lease_epoch: int
    required_argv_ids: tuple[str, ...]
    mode: str = "REQUEST_ONLY_NO_HOST_EXECUTION"
    guest_can_issue_receipt: bool = False
    host_fallback_allowed: bool = False


def prepare_review_request(
    *, task_id: str, run_id: str, candidate_sha: str,
    source_sha: str, plan_sha256: str, lease_epoch: int,
    trusted_required_argv_ids: tuple[str, ...],
) -> ReviewRequest:
    for value in (task_id, run_id):
        if not isinstance(value, str) or not _ID.fullmatch(value):
            raise ValueError("invalid trusted review identity")
    if (not isinstance(candidate_sha, str) or not _SHA40.fullmatch(candidate_sha)
        or not isinstance(source_sha, str) or not _SHA40.fullmatch(source_sha)
        or not isinstance(plan_sha256, str) or not _SHA64.fullmatch(plan_sha256)
        or type(lease_epoch) is not int or lease_epoch <= 0):
        raise ValueError("invalid pinned trusted review context")
    ids = trusted_required_argv_ids
    if (not isinstance(ids, tuple) or not 1 <= len(ids) <= 32
        or any(not isinstance(i, str) or not _ID.fullmatch(i) for i in ids)
        or len(set(ids)) != len(ids)):
        raise ValueError("mandatory checks must come from trusted policy")
    return ReviewRequest(task_id, run_id, candidate_sha, source_sha,
                         plan_sha256, lease_epoch, ids)


# Original code for a predeclared, exact-argv reviewer policy. This module
# cannot verify an OS principal or execute commands. A future independent
# protected Windows reviewer must pin the executable hashes, container
# identity, lease and protected signer before running *any* check.
from hashlib import sha256 as _sha256
import json as _json


class ReviewPlanHold(ValueError):
    """Do not emit untrusted commands or claim independent F18 verification."""


@dataclass(frozen=True)
class MandatoryCheck:
    check_id: str
    argv: tuple[str, ...]
    timeout_seconds: int
    no_network: bool = True


@dataclass(frozen=True)
class ReviewerPolicy:
    policy_sha256: str
    checks: tuple[MandatoryCheck, ...]
    required_env_keys: tuple[str, ...] = ("PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE")
    state: str = "SOURCE_POLICY_NOT_OS_ATTESTED"
    can_execute: bool = False


@dataclass(frozen=True)
class IsolatedReviewerIntent:
    task_id: str
    run_id: str
    plan_sha256: str
    source_sha: str
    candidate_sha: str
    lease_epoch: int
    policy_sha256: str
    reviewer_binary_sha256: str
    check_ids: tuple[str, ...]
    state: str = "HOLD_UNTIL_INDEPENDENT_OS_REVIEWER"
    executable: bool = False
    can_issue_trusted_receipt: bool = False
    host_fallback: bool = False


def build_reviewer_policy(
    *, syntax_checks: bool = True,
    unit_checks: bool = True,
    security_checks: bool = True,
) -> ReviewerPolicy:
    """Literal, fixed reviewer checks: not caller-supplied shell/argv.

    Unit/security tests may contain hostile model-authored code: they MUST
    execute under the separately protected independent sandbox, not here.
    """
    if any(type(v) is not bool for v in (syntax_checks,unit_checks,security_checks)):
        raise ReviewPlanHold("invalid policy flags")
    allowed = (
        MandatoryCheck("SYNTAX-001", ("python", "-I", "-m", "compileall", "-q", "src"), 60),
        MandatoryCheck("UNIT-001", ("python", "-I", "-m", "unittest", "discover",
                                    "-s", "tests/unit", "-p", "test_*.py", "-v"), 180),
        MandatoryCheck("SECURITY-001", ("python", "-I", "-m", "unittest", "discover",
                                        "-s", "tests/security", "-p", "test_*.py", "-v"), 180),
    )
    selected = tuple(check for check, use in zip(
        allowed,(syntax_checks,unit_checks,security_checks)
    ) if use)
    # For real F18 acceptance all mandatory checks must be present.
    if len(selected) != 3:
        raise ReviewPlanHold("mandatory review check omitted")
    canonical = _json.dumps(
        [{"id":c.check_id,"argv":c.argv,"timeout":c.timeout_seconds,
          "no_network":c.no_network} for c in selected],
        sort_keys=True,separators=(",",":"),ensure_ascii=True,
    ).encode("ascii")
    return ReviewerPolicy(_sha256(b"mla-review-policy/v1|" + canonical).hexdigest(), selected)


def plan_isolated_reviewer(
    request: ReviewRequest, policy: ReviewerPolicy, *,
    protected_reviewer_binary_sha256: str,
    trusted_source_sha: str, trusted_plan_sha256: str,
    trusted_candidate_sha: str,
) -> IsolatedReviewerIntent:
    """Produce *only* a HOLD intent; refuse policy/test argv injection.

    Caller-supplied SHA strings alone do not establish protected identity.
    """
    if not isinstance(request,ReviewRequest) or not isinstance(policy,ReviewerPolicy):
        raise ReviewPlanHold("untrusted request")
    approved=build_reviewer_policy()
    if (policy != approved or policy.can_execute
        or not isinstance(protected_reviewer_binary_sha256,str)
        or not _SHA64.fullmatch(protected_reviewer_binary_sha256)
        or request.source_sha != trusted_source_sha
        or request.plan_sha256 != trusted_plan_sha256
        or request.candidate_sha != trusted_candidate_sha
        or request.required_argv_ids != tuple(c.check_id for c in approved.checks)
        or request.guest_can_issue_receipt is not False
        or request.host_fallback_allowed is not False
        or request.mode != "REQUEST_ONLY_NO_HOST_EXECUTION"):
        raise ReviewPlanHold("protected reviewer context mismatch")
    return IsolatedReviewerIntent(
        request.task_id,request.run_id,request.plan_sha256,
        request.source_sha,request.candidate_sha,request.lease_epoch,
        policy.policy_sha256,protected_reviewer_binary_sha256,
        request.required_argv_ids,
    )
