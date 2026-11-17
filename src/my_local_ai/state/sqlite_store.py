"""Fail-closed SQLite state bootstrap on a locally owned, synthetic-first DB.

This module is NOT an OS-protected trust boundary. It rejects unknown database
ownership/schema, unsafe filesystem paths, and incomplete migrations. Windows
reparse and physical crash behavior remain P2 owner-device tests.
"""
from __future__ import annotations

from dataclasses import dataclass
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
    with path.open("rb") as handle:
        header = handle.read(100)
    if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
        raise ValueError("refusing unknown/non-SQLite existing state")
    app_id = int.from_bytes(header[68:72], "big")
    version = int.from_bytes(header[60:64], "big")
    if app_id != APP_ID or version not in (0, SCHEMA_VERSION):
        raise ValueError("refusing unowned or unsupported state version")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5.0) as read_only:
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
