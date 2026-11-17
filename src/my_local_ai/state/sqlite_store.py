"""Fail-closed SQLite state bootstrap on a locally owned, synthetic-first DB.

This module is NOT an OS-protected trust boundary. It rejects unknown database
ownership/schema, unsafe filesystem paths, and incomplete migrations. Windows
reparse and physical crash behavior remain P2 owner-device tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import uuid

from .migrations import (
    APP_ID, SCHEMA_VERSION, DDL, REQUIRED_TABLES,
    canonical_schema_sql, schema_sha256,
)

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass(frozen=True)
class SchemaReceipt:
    schema_version: int
    ddl_sha256: str
    backup_name: str | None
    wal_enabled: bool
    foreign_keys_enabled: bool
    backup_sha256: str | None = None


def _reject_link_or_alias(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & _REPARSE):
        raise ValueError("symlink/reparse state path")
    if path.suffix == ".sqlite3" or path.name.endswith((".sqlite3-wal", ".sqlite3-shm")):
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("state path must be a unique regular file")


def _safe_db_path(value: str | Path) -> Path:
    path = Path(value).absolute()
    if ".." in path.parts:
        raise ValueError("lexical parent traversal in state path")
    if path.suffix != ".sqlite3" or not path.parent.is_dir():
        raise ValueError("database must be a .sqlite3 file in an existing directory")
    for part in (path, *path.parents):
        _reject_link_or_alias(part)
    # SQLite may independently access these files; never follow a pre-existing
    # hostile WAL or SHM alias. This is not a substitute for protected OS ACLs.
    for suffix in ("-wal", "-shm"):
        _reject_link_or_alias(path.with_name(path.name + suffix))
    return path


def _identity(path: Path) -> tuple[int, int]:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("non-regular state")
    return (info.st_dev, info.st_ino)


def _check_integrity(db: sqlite3.Connection) -> None:
    try:
        result = db.execute("PRAGMA quick_check").fetchone()
        if result is None or result[0] != "ok":
            raise ValueError("state integrity failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("state foreign keys violated")
    except sqlite3.DatabaseError:
        raise ValueError("state integrity failed") from None


def _check_empty_v0(db: sqlite3.Connection) -> None:
    unexpected = db.execute(
        "SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
    ).fetchone()
    if unexpected is not None:
        raise ValueError("unknown v0 objects; migration held")


def _check_v1_schema(db: sqlite3.Connection) -> None:
    expected = canonical_schema_sql()
    objects = db.execute(
        "SELECT name, type, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
    ).fetchall()
    actual = {}
    for name, kind, ddl in objects:
        if not isinstance(ddl, str):
            raise ValueError("unsupported state schema object")
        actual[name] = (kind, " ".join(ddl.split()))
    if set(actual) != REQUIRED_TABLES or set(expected) != REQUIRED_TABLES:
        raise ValueError("state schema tables mismatch")
    if any(actual[name] != ("table", expected[name]) for name in expected):
        raise ValueError("state schema drift/trigger/index not approved")


def _inspect_existing(path: Path) -> int:
    # First verify the header without letting sqlite3 create/modify unknown DBs.
    # Do not follow a file replacement between lstat and the read.
    original = path.lstat()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (original.st_dev, original.st_ino)):
            raise ValueError("existing state identity changed")
        header = handle.read(100)
    after = path.lstat()
    if (after.st_dev, after.st_ino) != (original.st_dev, original.st_ino):
        raise ValueError("state path changed during inspection")
    if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
        raise ValueError("refusing unknown/non-SQLite existing state")
    app_id = int.from_bytes(header[68:72], "big")
    version = int.from_bytes(header[60:64], "big")
    if app_id != APP_ID or version not in (0, SCHEMA_VERSION):
        raise ValueError("refusing unowned or unsupported state version")
    # A sqlite Connection context manager commits/rolls back but does NOT close.
    # closing() releases WAL/SHM handles deterministically (important on Windows).
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5.0)) as read_only:
        _check_integrity(read_only)
        if version == 0:
            _check_empty_v0(read_only)
        else:
            _check_v1_schema(read_only)
    return version


def _backup_snapshot(path: Path) -> tuple[str, str]:
    # UUID + O_EXCL ensures a new backup name is never overwritten.
    target = path.with_name(path.name + ".before_v1." + uuid.uuid4().hex + ".sqlite3")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        source = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5.0)
        try:
            destination = sqlite3.connect(target, timeout=5.0)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
        with target.open("rb") as handle:
            checksum = hashlib.file_digest(handle, "sha256").hexdigest()
    except BaseException:
        # Cleanup affects only our freshly created UUID backup, never original.
        target.unlink(missing_ok=True)
        raise
    return (target.name, checksum)


def initialize_state(value: str | Path) -> SchemaReceipt:
    path = _safe_db_path(value)
    existed = path.exists()
    original_identity = _identity(path) if existed else None
    version = _inspect_existing(path) if existed else 0
    backup, backup_sha = _backup_snapshot(path) if existed and version == 0 else (None, None)
    # A separate process may replace the path after inspection. Reject an
    # obvious replacement; protected directory/ACL and adversarial TOCTOU
    # validation remain deliberately LOCKED until P2.
    _safe_db_path(path)
    if existed and _identity(path) != original_identity:
        raise ValueError("state file changed before migration")
    if not existed and path.exists():
        raise ValueError("state file appeared during initialization")
    connection = sqlite3.connect(path, isolation_level=None, timeout=5.0)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        journal = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower()
        connection.execute("PRAGMA synchronous=FULL")
        if journal != "wal" or connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ValueError("required WAL and foreign key protection missing")
        # One SQLite immediate writer transaction guards migration and receipts.
        connection.execute("BEGIN IMMEDIATE")
        try:
            if existed and _identity(path) != original_identity:
                raise ValueError("state file changed during migration")
            if version == 0:
                _check_empty_v0(connection)
                for statement in DDL:
                    connection.execute(statement)
                connection.execute(f"PRAGMA application_id={APP_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            _check_v1_schema(connection)
            _check_integrity(connection)
            if (connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION
                or connection.execute("PRAGMA application_id").fetchone()[0] != APP_ID):
                raise ValueError("state header changed during migration")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        return SchemaReceipt(
            schema_version=SCHEMA_VERSION,
            ddl_sha256=schema_sha256(),
            backup_name=backup,
            wal_enabled=True, foreign_keys_enabled=True,
            backup_sha256=backup_sha,
        )
    finally:
        connection.close()


# Local source-state writer. This API cannot grant owner authorization or VERIFIED.
# Only an already initialized MLA-owned database (exact schema/application ID)
# may be modified; never create/migrate a caller's original or external DB.
import re as _re
_MLA_ID = _re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_MLA_SHA40 = _re.compile(r"[0-9a-f]{40}\Z")
_MLA_SHA64 = _re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class LocalStateEvent:
    plan_id: str
    task_id: str
    state: str
    event_id: int | None
    changed: bool
    runtime_authorized: bool = False
    independently_verified: bool = False


def _write_owned_transaction(value: str | Path, operation):
    """Perform one atomic write to an existing, owned, unaliased MLA state DB."""
    path = _safe_db_path(value)
    if not path.exists() or _inspect_existing(path) != SCHEMA_VERSION:
        raise ValueError("MLA-owned initialized state database required")
    inode = _identity(path)
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True,
                                 isolation_level=None, timeout=5.0)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ValueError("foreign keys disabled")
        db.execute("BEGIN IMMEDIATE")
        try:
            if (_identity(path) != inode or
                db.execute("PRAGMA application_id").fetchone()[0] != APP_ID or
                db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
                raise ValueError("stale/unowned state")
            _check_v1_schema(db)
            result = operation(db)
            if _identity(path) != inode:
                raise ValueError("database identity changed")
            db.commit()
            return result
        except BaseException:
            db.rollback()
            raise


def persist_local_source_task(
    value: str | Path, *, plan_id: str, task_id: str,
    plan_sha256: str, source_sha: str, blueprint_sha: str,
    action: str = "REGISTER", expected_state: str | None = None,
) -> LocalStateEvent:
    """Register source metadata or HOLD a task; never mint a lease/VERIFIED.

    Registration is idempotent. A HOLD requires the exact expected prior state;
    no task can be silently reset from HOLD to READY/LEASED by this source port.
    """
    if (not isinstance(plan_id, str) or not _MLA_ID.fullmatch(plan_id)
        or not isinstance(task_id, str) or not _MLA_ID.fullmatch(task_id)
        or not isinstance(plan_sha256, str) or not _MLA_SHA64.fullmatch(plan_sha256)
        or not isinstance(source_sha, str) or not _MLA_SHA40.fullmatch(source_sha)
        or not isinstance(blueprint_sha, str) or not _MLA_SHA40.fullmatch(blueprint_sha)
        or action not in ("REGISTER", "HOLD")
        or (action == "HOLD" and expected_state not in {
            "HOLD", "QUEUED", "READY", "LEASED", "CODING", "REVIEW_PENDING",
            "REPAIR_ONCE", "INTERRUPTED", "BLOCKED_DEPENDENCY", "AWAITING_OWNER",
        })
        or (action == "REGISTER" and expected_state is not None)):
        raise ValueError("untrusted source-state transition")

    def change(db):
        plan = db.execute("SELECT plan_sha, blueprint_sha FROM plans WHERE plan_id=?",
                          (plan_id,)).fetchone()
        if plan is not None and plan != (plan_sha256, blueprint_sha):
            raise ValueError("stale plan identity")
        if plan is None and action != "REGISTER":
            raise ValueError("unknown plan")
        if plan is None:
            db.execute("INSERT INTO plans(plan_id,plan_sha,blueprint_sha) VALUES(?,?,?)",
                       (plan_id,plan_sha256,blueprint_sha))
        row = db.execute("SELECT source_sha,state FROM tasks WHERE plan_id=? AND task_id=?",
                         (plan_id,task_id)).fetchone()
        if row is None and action != "REGISTER":
            raise ValueError("unknown task")
        if row is None:
            db.execute("INSERT INTO tasks(plan_id,task_id,source_sha) VALUES(?,?,?)",
                       (plan_id,task_id,source_sha))
            state, changed = "QUEUED", True
        else:
            if row[0] != source_sha:
                raise ValueError("stale task source")
            state, changed = row[1], False
        if action == "HOLD" and state != "HOLD":
            if state != expected_state or state == "VERIFIED":
                raise ValueError("stale task state or trust boundary")
            db.execute("UPDATE tasks SET state='HOLD' WHERE plan_id=? AND task_id=? AND state=?",
                       (plan_id,task_id,expected_state))
            state, changed = "HOLD", True
        elif action == "HOLD" and state == "HOLD":
            if expected_state != "HOLD":
                raise ValueError("task already changed")
        event_id = None
        if changed:
            kind = "SOURCE_REGISTERED" if action == "REGISTER" else "SOURCE_HOLD"
            cursor = db.execute(
                "INSERT INTO events(plan_id,event_kind,safe_summary) VALUES(?,?,?)",
                (plan_id,kind,"SOURCE_ONLY_NO_OWNER_GRANT_OR_F18"),
            )
            event_id = cursor.lastrowid
        return LocalStateEvent(plan_id,task_id,state,event_id,changed)
    return _write_owned_transaction(value,change)


@dataclass(frozen=True)
class UntrustedRunEvent:
    run_id: str
    plan_id: str
    task_id: str
    candidate_sha: str | None
    changed: bool
    status: str = "UNTRUSTED_CANDIDATE_NOT_VERIFIED"
    allowed_to_integrate: bool = False


def persist_untrusted_candidate_run(
    value: str | Path, *, plan_id: str, task_id: str, run_id: str,
    source_sha: str, baseline_sha: str, lease_epoch: int,
    candidate_sha: str | None = None,
) -> UntrustedRunEvent:
    """Record a candidate run *without* minting leases, rights or trusted PASS.

    Durable run history may be written only for registered tasks with matching
    source; it cannot promote candidate code, original refs or owner consent.
    """
    if (not all(isinstance(x,str) and _MLA_ID.fullmatch(x)
                for x in (plan_id,task_id,run_id))
        or not isinstance(source_sha,str) or not _MLA_SHA40.fullmatch(source_sha)
        or not isinstance(baseline_sha,str) or not _MLA_SHA40.fullmatch(baseline_sha)
        or type(lease_epoch) is not int or not 1 <= lease_epoch < 2**63
        or (candidate_sha is not None and
            (not isinstance(candidate_sha,str) or not _MLA_SHA40.fullmatch(candidate_sha)))):
        raise ValueError("invalid untrusted run metadata")
    def change(db):
        task = db.execute("SELECT source_sha,state FROM tasks WHERE plan_id=? AND task_id=?",
                          (plan_id,task_id)).fetchone()
        if task is None or task[0] != source_sha or task[1] in ("HOLD","VERIFIED"):
            raise ValueError("unknown, stale or stopped task")
        old = db.execute(
            "SELECT plan_id,task_id,baseline_sha,lease_epoch,candidate_sha,state "
            "FROM runs WHERE run_id=?", (run_id,),
        ).fetchone()
        expected=(plan_id,task_id,baseline_sha,lease_epoch,candidate_sha,
                  "UNTRUSTED_CANDIDATE")
        if old is not None and old != expected:
            raise ValueError("run ID replay or stale candidate")
        if old is None:
            db.execute(
                "INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,"
                "state,candidate_sha) VALUES(?,?,?,?,?,?,?)",
                (run_id,plan_id,task_id,baseline_sha,lease_epoch,
                 "UNTRUSTED_CANDIDATE",candidate_sha),
            )
            db.execute(
                "INSERT INTO events(plan_id,event_kind,safe_summary) VALUES(?,?,?)",
                (plan_id,"UNTRUSTED_RUN_RECORDED","NO_LEASE_OR_F18_ASSERTED"),
            )
            if candidate_sha is not None:
                # A candidate can enter REVIEW_PENDING for independent
                # inspection. Neither this state nor the supplied SHA is PASS.
                db.execute(
                    "UPDATE tasks SET state='REVIEW_PENDING' WHERE plan_id=? "
                    "AND task_id=? AND state IN ('QUEUED','REVIEW_PENDING')",
                    (plan_id,task_id),
                )
            db.execute(
                "INSERT INTO attempts(run_id,attempt_number,state) VALUES(?,?,?)",
                (run_id,1,"UNTRUSTED_CANDIDATE"),
            )
        return UntrustedRunEvent(run_id,plan_id,task_id,candidate_sha,old is None)
    return _write_owned_transaction(value,change)


@dataclass(frozen=True)
class UntrustedRepairOffer:
    run_id: str
    task_id: str
    offer_sha256: str
    newly_recorded: bool
    protected_owner_granted: bool = False
    may_execute_repair: bool = False


def persist_local_repair_offer(
    value: str | Path, *, plan_id: str, task_id: str, run_id: str,
    plan_sha256: str, baseline_sha: str, candidate_sha: str,
    failure_sha256: str, strategy: str,
) -> UntrustedRepairOffer:
    """Record second-attempt proposal only. Task remains HOLD, not executable.

    This does not manufacture owner signature, lease generation or F18 PASS.
    Actual improvement execution requires a later protected decision.
    """
    if (not all(isinstance(x,str) and _MLA_ID.fullmatch(x)
                for x in (plan_id,task_id,run_id))
        or not isinstance(plan_sha256,str) or not _MLA_SHA64.fullmatch(plan_sha256)
        or not isinstance(baseline_sha,str) or not _MLA_SHA40.fullmatch(baseline_sha)
        or not isinstance(candidate_sha,str) or not _MLA_SHA40.fullmatch(candidate_sha)
        or not isinstance(failure_sha256,str) or not _MLA_SHA64.fullmatch(failure_sha256)
        or strategy not in {
            "LIMITED_SYNTAX_REPAIR","ISOLATED_UNIT_FIX",
            "NARROW_PERMISSION_FIX","CONTRACT_SCOPE_CORRECTION",
            "REDUCE_BATCH_MEMORY",
        }):
        raise ValueError("invalid source repair offer")
    digest=hashlib.sha256((
        "mla-repair-offer/v1|" + plan_sha256 + "|" + run_id + "|" +
        candidate_sha + "|" + failure_sha256 + "|" + strategy
    ).encode("ascii")).hexdigest()
    label="UNTRUSTED_OFFER_HOLD_" + digest

    def change(db):
        row=db.execute(
            "SELECT r.plan_id,r.task_id,r.baseline_sha,r.candidate_sha,"
            "t.state,p.plan_sha FROM runs r "
            "JOIN tasks t ON t.plan_id=r.plan_id AND t.task_id=r.task_id "
            "JOIN plans p ON p.plan_id=r.plan_id WHERE r.run_id=?",
            (run_id,),
        ).fetchone()
        if row != (plan_id,task_id,baseline_sha,candidate_sha,"HOLD",plan_sha256):
            raise ValueError("stale run or protected state")
        first=db.execute("SELECT state FROM attempts WHERE run_id=? AND attempt_number=1",
                         (run_id,)).fetchone()
        if first is None or first[0] != "UNTRUSTED_CANDIDATE":
            raise ValueError("unrecorded first attempt")
        previous=db.execute("SELECT state FROM attempts WHERE run_id=? AND attempt_number=2",
                            (run_id,)).fetchone()
        if previous is not None and previous[0] != label:
            raise ValueError("repair offer replay with different evidence")
        if previous is None:
            db.execute(
                "INSERT INTO attempts(run_id,attempt_number,state) VALUES(?,?,?)",
                (run_id,2,label),
            )
            db.execute(
                "INSERT INTO events(plan_id,event_kind,safe_summary) VALUES(?,?,?)",
                (plan_id,"REPAIR_OFFER_HELD","NO_OWNER_GO_NO_F18"),
            )
        return UntrustedRepairOffer(run_id,task_id,digest,previous is None)
    return _write_owned_transaction(value,change)
