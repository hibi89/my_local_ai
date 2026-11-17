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
