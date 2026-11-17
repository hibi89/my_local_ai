"""Lease generation fencing for a protected owner-side scheduler (P1 code).

This is an ORIGINAL, non-executing contract implementation. A model or guest
may not issue leases or treat an old run as verified. No DB mutations, model
calls, shell, OS operations, Git ref changes or owner authorization here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


class LeaseHold(ValueError):
    def __init__(self, reason="LEASE_FENCED"):
        self.code = reason if reason in {
            "LEASE_FENCED", "STALE_SOURCE", "ACTIVE_LEASE",
            "DUPLICATE_RUN", "INVALID_CONTEXT", "UNTRUSTED_STATE",
        } else "LEASE_FENCED"
        super().__init__(self.code)


@dataclass(frozen=True)
class LeaseSnapshot:
    plan_id: str
    task_id: str
    plan_sha: str
    baseline_sha: str
    existing_epoch: int
    active_run_id: str | None = None
    active_state: str | None = None


@dataclass(frozen=True)
class LeaseProposal:
    plan_id: str
    task_id: str
    baseline_sha: str
    expected_previous_epoch: int
    proposed_epoch: int
    idempotency_key: str
    state: str = "AWAIT_PROTECTED_TRANSACTION"
    runnable: bool = False
    owner_approved: bool = False


def propose_lease(snapshot: LeaseSnapshot, *, trusted_plan_sha: str,
                  trusted_baseline_sha: str) -> LeaseProposal:
    if not isinstance(snapshot, LeaseSnapshot):
        raise LeaseHold("INVALID_CONTEXT")
    if (not isinstance(snapshot.plan_id, str) or not _ID.fullmatch(snapshot.plan_id)
        or not isinstance(snapshot.task_id, str) or not _ID.fullmatch(snapshot.task_id)
        or not isinstance(snapshot.plan_sha, str) or not _SHA64.fullmatch(snapshot.plan_sha)
        or not isinstance(snapshot.baseline_sha, str) or not _SHA40.fullmatch(snapshot.baseline_sha)
        or type(snapshot.existing_epoch) is not int or not 0 <= snapshot.existing_epoch < 2**63 - 1):
        raise LeaseHold("INVALID_CONTEXT")
    if snapshot.plan_sha != trusted_plan_sha or snapshot.baseline_sha != trusted_baseline_sha:
        raise LeaseHold("STALE_SOURCE")
    if snapshot.active_run_id is not None or snapshot.active_state is not None:
        if snapshot.active_run_id is None or snapshot.active_state is None:
            raise LeaseHold("UNTRUSTED_STATE")
        if not _ID.fullmatch(snapshot.active_run_id):
            raise LeaseHold("UNTRUSTED_STATE")
        # Every active or unresolved lease must be dispositioned by protected
        # controller & independent verifier before a new epoch may be issued.
        raise LeaseHold("ACTIVE_LEASE")
    digest=hashlib.sha256(
        f"mla-lease/v1|{snapshot.plan_sha}|{snapshot.task_id}|"
        f"{snapshot.baseline_sha}|{snapshot.existing_epoch + 1}".encode("ascii")
    ).hexdigest()
    return LeaseProposal(snapshot.plan_id, snapshot.task_id,
                         snapshot.baseline_sha, snapshot.existing_epoch,
                         snapshot.existing_epoch + 1, digest)


def check_lease_fence(*, expected_run_id: str, expected_epoch: int,
                      observed_run_id: str, observed_epoch: int) -> bool:
    if (not isinstance(expected_run_id, str) or not _ID.fullmatch(expected_run_id)
        or type(expected_epoch) is not int or expected_epoch <= 0
        or not isinstance(observed_run_id, str) or type(observed_epoch) is not int):
        return False
    return expected_run_id == observed_run_id and expected_epoch == observed_epoch
