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
from .migrations import APP_ID, SCHEMA_VERSION, REQUIRED_TABLES, canonical_schema_sql

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
        # An attached DB or TEMP table can shadow unqualified plans/tasks
        # despite a legitimate application_id in main. Never trust them.
        attached = db.execute("PRAGMA database_list").fetchall()
        # SQLite lazily registers an empty built-in TEMP schema after the
        # first sqlite_temp_master read. It is safe only when empty.
        if (not 1 <= len(attached) <= 2 or attached[0][1] != "main"
            or any(item[1] not in {"main", "temp"} for item in attached)
            or len({item[1] for item in attached}) != len(attached)):
            raise ReconcileHold("BAD_STATE")
        if db.execute("SELECT 1 FROM sqlite_temp_master LIMIT 1").fetchone():
            raise ReconcileHold("BAD_STATE")
        expected = canonical_schema_sql()
        objects = db.execute(
            "SELECT name,type,sql FROM main.sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        actual = {
            name: (kind, " ".join(sql.split()) if isinstance(sql, str) else None)
            for name, kind, sql in objects
        }
        if (set(actual) != REQUIRED_TABLES or
            any(actual.get(name) != ("table", statement) for name, statement in expected.items())):
            raise ReconcileHold("BAD_STATE")
        if (db.execute("PRAGMA quick_check").fetchone() != ("ok",)
            or db.execute("PRAGMA foreign_key_check").fetchone() is not None):
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

        # Scan all current/task history before deciding whether interrupted
        # work can safely be retried. A DB 'TRUSTED_PASS' string is NOT F18.
        historical = db.execute(
            "SELECT run_id,baseline_sha,lease_epoch,state,candidate_sha FROM runs "
            "WHERE plan_id=? AND task_id=? ORDER BY lease_epoch",
            (plan_id,task_id),
        ).fetchall()
        epochs: set[int] = set()
        run_index = {}
        for run_id,source,epoch,state,candidate_sha in historical:
            if (not isinstance(run_id,str) or not _ID.fullmatch(run_id)
                or not isinstance(source,str) or source!=trusted_source_sha
                or type(epoch) is not int or epoch<=0 or epoch in epochs
                or state not in ("LEASE_RESERVED_UNVERIFIED","UNTRUSTED_CANDIDATE",
                                 "REVIEW_PENDING","INTERRUPTED","HOLD",
                                 "CODING","REPAIR_ONCE","VERIFIED")
                or (candidate_sha is not None and (
                    not isinstance(candidate_sha,str) or not _SHA40.fullmatch(candidate_sha)))):
                raise ReconcileHold("BAD_STATE")
            epochs.add(epoch)
            run_index[run_id]=(source,epoch,state,candidate_sha)
        integrated = db.execute(
            "SELECT i.integrated_sha,i.local_ref,rv.result,rv.candidate_sha,"
            "r.run_id,r.baseline_sha,r.candidate_sha FROM integrations i "
            "JOIN reviews rv ON rv.review_id=i.review_id "
            "JOIN runs r ON r.run_id=rv.run_id "
            "WHERE r.plan_id=? AND r.task_id=?",
            (plan_id,task_id),
        ).fetchall()
        if len(integrated)>1:
            raise ReconcileHold("BAD_STATE")
        # A review without its integration is a partial crash boundary, not
        # permission to start another worker. Orphan/duplicate review states
        # cannot be used as standalone F18 proof.
        reviews = db.execute(
            "SELECT rv.review_id,rv.run_id,rv.candidate_sha,rv.result "
            "FROM reviews rv JOIN runs r ON rv.run_id=r.run_id "
            "WHERE r.plan_id=? AND r.task_id=?",
            (plan_id,task_id),
        ).fetchall()
        if len(reviews)>1 or (integrated and len(reviews)!=1):
            raise ReconcileHold("INCOMPLETE_TRUST_EVIDENCE")
        exact_ref = "refs/heads/mla/isolated/" + task_id
        all_ref_claims = db.execute(
            "SELECT COUNT(*) FROM integrations WHERE local_ref=?", (exact_ref,)
        ).fetchone()[0]
        if type(all_ref_claims) is not int or all_ref_claims != len(integrated):
            raise ReconcileHold("BAD_STATE")
        if rows:
            epoch,run_id=rows[0]
            info=run_index.get(run_id)
            if (not info or not check_lease_fence(
                expected_run_id=run_id,expected_epoch=epoch,
                observed_run_id=run_id,observed_epoch=info[1],
            )):
                raise ReconcileHold("STALE_LEASE")
            if info[2] not in ("REVIEW_PENDING","INTERRUPTED","HOLD","CODING","REPAIR_ONCE"):
                raise ReconcileHold("BAD_STATE")
            if epochs and epoch != max(epochs):
                raise ReconcileHold("STALE_LEASE")
            # A completed integration and an active coding lease cannot be
            # reconciled without a separate protected DB/Git transaction log.
            if integrated:
                raise ReconcileHold("INCOMPLETE_TRUST_EVIDENCE")
            if tasks[0][1] == "VERIFIED":
                raise ReconcileHold("UNTRUSTED_VERIFIED")
            return ReconcileDecision(task_id,"HOLD_INTERRUPTED_LEASE")
        if integrated:
            integrated_sha,local_ref,review_status,review_sha,run_id,run_source,run_sha=integrated[0]
            if (not isinstance(integrated_sha,str) or not _SHA40.fullmatch(integrated_sha)
                or not isinstance(local_ref,str)
                or local_ref != exact_ref
                or reviews[0][1] != run_id
                or not isinstance(run_source,str) or run_source != trusted_source_sha
                or review_status != "TRUSTED_PASS"
                or integrated_sha != review_sha or integrated_sha != run_sha
                or run_id not in run_index):
                raise ReconcileHold("UNTRUSTED_VERIFIED")
            if protected_ref_sha!=integrated_sha:
                raise ReconcileHold("REF_MISMATCH")
            return ReconcileDecision(task_id,"PRESERVE_PREVIOUS_REF_AWAIT_F18")
        if protected_ref_sha is not None:
            raise ReconcileHold("REF_MISMATCH")
        if reviews:
            return ReconcileDecision(task_id, "HOLD_PARTIAL_REVIEW_REQUIRES_F18")
        if tasks[0][1] == "VERIFIED":
            raise ReconcileHold("UNTRUSTED_VERIFIED")
        if historical:
            # Crash between run creation and lease insertion, or a stale run
            # whose lease disappeared, cannot be silently restarted.
            return ReconcileDecision(task_id,"HOLD_ORPHAN_RUN_REQUIRES_FENCE")
        if plans[0][2] != "APPROVED":
            return ReconcileDecision(task_id,"HOLD_PLAN_NOT_APPROVED")
        return ReconcileDecision(task_id,"HOLD_NO_ACTIVE_LEASE")
    except sqlite3.Error:
        raise ReconcileHold("BAD_STATE") from None


@dataclass(frozen=True)
class DurableRecoveryResult:
    task_id: str
    decision: str
    checkpoint_written: bool
    run_id: str | None = None
    generation: int | None = None
    execution_allowed: bool = False
    new_lease_allowed: bool = False
    may_change_git_ref: bool = False
    independently_verified: bool = False


def reconcile_owned_crash_checkpoint(
    db_path, *, plan_id: str, task_id: str, trusted_plan_sha: str,
    trusted_source_sha: str, protected_ref_sha: str | None,
    interrupted_run_id: str | None = None,
    interrupted_generation: int | None = None,
) -> DurableRecoveryResult:
    """Read exact owned state and optionally persist one interruption HOLD.

    The Git ref value must originate from an owner-protected reader. Supplying
    it does not make this routine an independent reviewer or grant a resume.
    No clean ref or unchanged DB can be upgraded into a verified receipt.
    """
    from contextlib import closing
    from pathlib import Path
    from my_local_ai.state.sqlite_store import (
        _safe_db_path, _inspect_existing, _identity,
        persist_owned_interrupted_checkpoint,
    )

    try:
        path = _safe_db_path(db_path)
        if not path.exists() or _inspect_existing(path) != SCHEMA_VERSION:
            raise ReconcileHold("BAD_STATE")
        before = _identity(path)
        with closing(sqlite3.connect(
            path.as_uri() + "?mode=ro", uri=True, timeout=5.0,
        )) as db:
            db.execute("PRAGMA query_only=ON")
            decision = read_reconcile_state(
                db, plan_id=plan_id, task_id=task_id,
                trusted_plan_sha=trusted_plan_sha,
                trusted_source_sha=trusted_source_sha,
                protected_ref_sha=protected_ref_sha,
            )
        if _identity(path) != before:
            raise ReconcileHold("BAD_STATE")
        if (interrupted_run_id is None) != (interrupted_generation is None):
            raise ReconcileHold("STALE_LEASE")
        if interrupted_run_id is None:
            return DurableRecoveryResult(task_id, decision.status, False)
        if decision.status != "HOLD_INTERRUPTED_LEASE" or protected_ref_sha is not None:
            raise ReconcileHold("INCOMPLETE_TRUST_EVIDENCE")
        checkpoint = persist_owned_interrupted_checkpoint(
            path, plan_id=plan_id, task_id=task_id,
            run_id=interrupted_run_id,
            plan_sha256=trusted_plan_sha, baseline_sha=trusted_source_sha,
            expected_generation=interrupted_generation,
        )
        return DurableRecoveryResult(
            task_id, checkpoint.status, checkpoint.changed,
            checkpoint.run_id, checkpoint.lease_generation,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        if isinstance(exc, ReconcileHold):
            raise
        raise ReconcileHold("BAD_STATE") from None
