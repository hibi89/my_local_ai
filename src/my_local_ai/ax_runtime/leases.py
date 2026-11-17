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
        f"mla-lease/v2|{snapshot.plan_id}|{snapshot.plan_sha}|{snapshot.task_id}|"
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


# P1 synthetic-only SQLite transaction. The in-memory restriction means no
# customer/owner database can be changed by this API. A protected Windows
# owner signer + actual isolated worker gate is a separate production port.
import sqlite3
from my_local_ai.contracts.approval import OwnerGrant, authorize_claim
from my_local_ai.state.migrations import APP_ID, SCHEMA_VERSION


@dataclass(frozen=True)
class SyntheticLeaseReceipt:
    run_id: str
    task_id: str
    lease_epoch: int
    state: str = "SYNTHETIC_LEASED_UNVERIFIED"
    can_run_coder: bool = False
    can_update_original: bool = False


def claim_synthetic_lease(
    db: sqlite3.Connection, proposal: LeaseProposal, *,
    run_id: str, plan_sha256: str, source_sha: str,
    owner_grant: OwnerGrant | None, trusted_test_key: bytes | None,
    trusted_live_consent_check, now_seconds: int,
) -> SyntheticLeaseReceipt:
    """One atomic lease claim on an in-memory fixture, never on an OS database.

    The transaction is a semantics smoke. It cannot establish signer identity
    or permit real model execution. Future owner-runtime path must enforce an
    OS-protected database and real independent F18 gate.
    """
    if not isinstance(db,sqlite3.Connection) or not isinstance(proposal,LeaseProposal):
        raise LeaseHold("INVALID_CONTEXT")
    if (not isinstance(run_id,str) or not _ID.fullmatch(run_id)
        or not isinstance(plan_sha256,str) or not _SHA64.fullmatch(plan_sha256)
        or not isinstance(source_sha,str) or not _SHA40.fullmatch(source_sha)
        or not isinstance(proposal.plan_id,str) or not _ID.fullmatch(proposal.plan_id)
        or not isinstance(proposal.task_id,str) or not _ID.fullmatch(proposal.task_id)
        or not isinstance(proposal.baseline_sha,str) or not _SHA40.fullmatch(proposal.baseline_sha)
        or proposal.baseline_sha != source_sha
        or type(proposal.expected_previous_epoch) is not int
        or proposal.expected_previous_epoch < 0
        or type(proposal.proposed_epoch) is not int
        or proposal.proposed_epoch != proposal.expected_previous_epoch + 1
        or not isinstance(proposal.idempotency_key,str)
        or not _SHA64.fullmatch(proposal.idempotency_key)
        or proposal.idempotency_key != hashlib.sha256(
            f"mla-lease/v2|{proposal.plan_id}|{plan_sha256}|{proposal.task_id}|"
            f"{source_sha}|{proposal.proposed_epoch}".encode("ascii")
        ).hexdigest()
        or type(now_seconds) is not int or now_seconds <= 0):
        raise LeaseHold("INVALID_CONTEXT")
    # Production-file and even temp-disk databases are categorically refused.
    # Attacker-controlled URI modes and attached databases are also refused.
    try:
        files=db.execute("PRAGMA database_list").fetchall()
        if (len(files)!=1 or files[0][1]!="main" or files[0][2]!=""
            or db.in_transaction or db.execute("PRAGMA query_only").fetchone()[0]!=0
            or db.execute("PRAGMA application_id").fetchone()[0]!=APP_ID
            or db.execute("PRAGMA user_version").fetchone()[0]!=SCHEMA_VERSION
            or db.execute("PRAGMA foreign_keys").fetchone()[0]!=1):
            raise LeaseHold("INVALID_CONTEXT")
    except sqlite3.Error:
        raise LeaseHold("INVALID_CONTEXT") from None
    if not authorize_claim(
        owner_grant,trusted_hmac_key=trusted_test_key,
        expected_plan_sha=plan_sha256,expected_source_sha=source_sha,
        required_scope="LOCAL_PLAN",now_seconds=now_seconds,
        trusted_live_consent_check=trusted_live_consent_check,
    ):
        raise LeaseHold("UNTRUSTED_STATE")
    try:
        db.execute("BEGIN IMMEDIATE")
        plan=db.execute(
            "SELECT plan_sha,blueprint_sha,state FROM plans WHERE plan_id=?",
            (proposal.plan_id,),
        ).fetchall()
        task=db.execute(
            "SELECT source_sha,state FROM tasks WHERE plan_id=? AND task_id=?",
            (proposal.plan_id,proposal.task_id),
        ).fetchall()
        consent=db.execute(
            "SELECT state FROM owner_consents WHERE consent_id=? AND plan_sha=? AND scope='LOCAL_PLAN'",
            (owner_grant.grant_id,plan_sha256),
        ).fetchall()
        if (len(plan)!=1 or len(task)!=1 or len(consent)!=1
            or plan[0] != (plan_sha256,source_sha,"APPROVED")
            or task[0] != (source_sha,"READY")
            or consent[0] != ("APPROVED",)):
            raise LeaseHold("UNTRUSTED_STATE")
        existing=db.execute(
            "SELECT run_id FROM leases WHERE plan_id=? AND task_id=?",
            (proposal.plan_id,proposal.task_id),
        ).fetchall()
        highest=db.execute(
            "SELECT COALESCE(MAX(lease_epoch),0) FROM runs WHERE plan_id=? AND task_id=?",
            (proposal.plan_id,proposal.task_id),
        ).fetchone()[0]
        if existing:
            raise LeaseHold("ACTIVE_LEASE")
        if (type(highest) is not int or highest != proposal.expected_previous_epoch
            or proposal.proposed_epoch != highest+1):
            raise LeaseHold("LEASE_FENCED")
        if db.execute("SELECT 1 FROM runs WHERE run_id=?",(run_id,)).fetchone():
            raise LeaseHold("DUPLICATE_RUN")
        db.execute(
            "INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,state) "
            "VALUES(?,?,?,?,?,'REVIEW_PENDING')",
            (run_id,proposal.plan_id,proposal.task_id,source_sha,proposal.proposed_epoch),
        )
        db.execute(
            "INSERT INTO leases(plan_id,task_id,generation,run_id) VALUES(?,?,?,?)",
            (proposal.plan_id,proposal.task_id,proposal.proposed_epoch,run_id),
        )
        updated=db.execute(
            "UPDATE tasks SET state='LEASED' WHERE plan_id=? AND task_id=? AND state='READY'",
            (proposal.plan_id,proposal.task_id),
        )
        if updated.rowcount!=1:
            raise LeaseHold("LEASE_FENCED")
        db.commit()
        return SyntheticLeaseReceipt(run_id,proposal.task_id,proposal.proposed_epoch)
    except (sqlite3.Error,LeaseHold):
        db.rollback()
        raise LeaseHold("LEASE_FENCED") from None
