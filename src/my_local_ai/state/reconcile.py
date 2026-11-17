"""Read-only SQLite+Git crash reconciliation. Never auto-approve, commit or resume.

Injected connection must be protected and query_only. Any untrusted lease,
guest-owned review or partial DB/Git transaction => HOLD. Verified ref may
be *preserved* but NEVER promoted on model/DB evidence alone.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3

from my_local_ai.ax_runtime.leases import check_lease_fence
from .migrations import APP_ID, SCHEMA_VERSION

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


class ReconcileHold(ValueError):
    def __init__(self, reason="INCOMPLETE_TRUST_EVIDENCE"):
        self.code = reason if reason in {
            "INCOMPLETE_TRUST_EVIDENCE", "BAD_STATE", "STALE_PLAN",
            "REF_MISMATCH", "STALE_LEASE", "UNTRUSTED_VERIFIED",
        } else "INCOMPLETE_TRUST_EVIDENCE"
        super().__init__(self.code)


@dataclass(frozen=True)
class ReconcileDecision:
    task_id: str
    status: str
    local_verified_ref_must_remain_unchanged: bool = True
    new_lease_allowed: bool = False
    git_write_allowed: bool = False
    executable: bool = False
    independently_verified: bool = False


def read_reconcile_state(
    db: sqlite3.Connection, *, plan_id: str, task_id: str,
    trusted_plan_sha: str, trusted_source_sha: str,
    protected_ref_sha: str | None,
) -> ReconcileDecision:
    """Only inspect, never execute or repair SQLite/Git.

    The protected caller provides the actual ref readback; a guest-supplied
    value is not independent evidence, thus every decision is HOLD/READ_ONLY.
    """
    if (not isinstance(db, sqlite3.Connection)
        or not isinstance(plan_id, str) or not _ID.fullmatch(plan_id)
        or not isinstance(task_id, str) or not _ID.fullmatch(task_id)
        or not isinstance(trusted_plan_sha, str) or not _SHA64.fullmatch(trusted_plan_sha)
        or not isinstance(trusted_source_sha, str) or not _SHA40.fullmatch(trusted_source_sha)
        or (protected_ref_sha is not None and
            (not isinstance(protected_ref_sha, str) or not _SHA40.fullmatch(protected_ref_sha)))):
        raise ReconcileHold("BAD_STATE")
    try:
        if (db.execute("PRAGMA query_only").fetchone()[0] != 1
            or db.execute("PRAGMA application_id").fetchone()[0] != APP_ID
            or db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
            raise ReconcileHold("BAD_STATE")
        plans = db.execute("SELECT plan_sha,blueprint_sha,state FROM plans WHERE plan_id=?",
                           (plan_id,)).fetchall()
        tasks = db.execute("SELECT source_sha,state FROM tasks WHERE plan_id=? AND task_id=?",
                           (plan_id,task_id)).fetchall()
        if len(plans)!=1 or len(tasks)!=1:
            raise ReconcileHold("BAD_STATE")
        if plans[0][0]!=trusted_plan_sha or tasks[0][0]!=trusted_source_sha or plans[0][1]!=trusted_source_sha:
            raise ReconcileHold("STALE_PLAN")
        rows = db.execute("SELECT generation,run_id FROM leases WHERE plan_id=? AND task_id=?",
                          (plan_id,task_id)).fetchall()
        if len(rows)>1:
            raise ReconcileHold("BAD_STATE")
        if rows:
            epoch,run_id=rows[0]
            runs = db.execute("SELECT baseline_sha,lease_epoch,state,candidate_sha FROM runs WHERE run_id=? AND plan_id=? AND task_id=?",
                              (run_id,plan_id,task_id)).fetchall()
            if (len(runs)!=1 or not check_lease_fence(
                expected_run_id=run_id,expected_epoch=epoch,
                observed_run_id=run_id,observed_epoch=runs[0][1],
            ) or runs[0][0]!=trusted_source_sha):
                raise ReconcileHold("STALE_LEASE")
            if runs[0][2] not in ("REVIEW_PENDING","INTERRUPTED","HOLD","CODING","REPAIR_ONCE"):
                raise ReconcileHold("BAD_STATE")
            # No reactivation after crash without protected grant and new lease.
            return ReconcileDecision(task_id,"HOLD_INTERRUPTED_LEASE")
        # Read prior integrations strictly for cross-resource inconsistency.
        integrated = db.execute(
            "SELECT i.integrated_sha FROM integrations i "
            "JOIN reviews rv ON rv.review_id=i.review_id "
            "JOIN runs r ON r.run_id=rv.run_id "
            "WHERE r.plan_id=? AND r.task_id=?",
            (plan_id,task_id),
        ).fetchall()
        if len(integrated)>1:
            raise ReconcileHold("BAD_STATE")
        if integrated:
            previously_integrated=integrated[0][0]
            if not isinstance(previously_integrated,str) or not _SHA40.fullmatch(previously_integrated):
                raise ReconcileHold("BAD_STATE")
            if protected_ref_sha!=previously_integrated:
                raise ReconcileHold("REF_MISMATCH")
            return ReconcileDecision(task_id,"PRESERVE_PREVIOUS_REF_AWAIT_F18")
        if protected_ref_sha is not None:
            # Ref exists without this task's matching durable integration.
            raise ReconcileHold("REF_MISMATCH")
        return ReconcileDecision(task_id,"HOLD_NO_ACTIVE_LEASE")
    except sqlite3.Error:
        raise ReconcileHold("BAD_STATE") from None
