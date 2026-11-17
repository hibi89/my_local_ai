"""Local SQLite state bootstrap with fail-closed ownership and backup before migration.

Bootstrap does not run arbitrary SQL from plans or touch user/customer databases.
Windows reparse isolation must be separately verified in P2.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import stat
import uuid

from .migrations import APP_ID, SCHEMA_VERSION, DDL, REQUIRED_TABLES, schema_sha256

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

@dataclass(frozen=True)
class SchemaReceipt:
    schema_version: int
    ddl_sha256: str
    backup_name: str | None
    wal_enabled: bool
    foreign_keys_enabled: bool

def _safe_db_path(value: str | Path) -> Path:
    path = Path(value).absolute()
    if path.suffix != ".sqlite3" or not path.parent.is_dir():
        raise ValueError("database must be a .sqlite3 file in an existing directory")
    # lstat each ancestor: symlinks and Windows junctions are not an acceptable state root.
    for part in (path, *path.parents):
        if not part.exists() and not part.is_symlink():
            continue
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_file_attributes & _REPARSE if hasattr(info, "st_file_attributes") else stat.S_ISLNK(info.st_mode):
            raise ValueError("symlink/reparse state path")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("database is not a unique regular file")
    return path

def _inspect_existing(path: Path) -> int:
    # SQLite header is inspected before connect/PRAGMA to avoid mutating an unknown DB.
    with path.open("rb") as handle:
        header = handle.read(100)
    if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
        raise ValueError("refusing unknown/non-SQLite existing state")
    app_id = int.from_bytes(header[68:72], "big")
    version = int.from_bytes(header[60:64], "big")
    if app_id != APP_ID or version not in (0, SCHEMA_VERSION):
        raise ValueError("refusing unowned or unsupported state version")
    return version

def _backup_snapshot(path: Path) -> str:
    target = path.with_name(path.name + ".before_v1." + uuid.uuid4().hex + ".sqlite3")
    source = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5.0)
    try:
        with sqlite3.connect(target, timeout=5.0) as destination:
            source.backup(destination)
    except Exception:
        if target.exists():
            target.unlink()
        raise
    finally:
        source.close()
    return target.name

def initialize_state(value: str | Path) -> SchemaReceipt:
    path = _safe_db_path(value)
    existed = path.exists()
    version = _inspect_existing(path) if existed else 0
    if existed and version == 0:
        # Only our own v0 empty schema may migrate; no arbitrary legacy tables.
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as old:
            existing_tables = {r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if existing_tables:
            raise ValueError("unknown v0 tables; migration held")
    backup = _backup_snapshot(path) if existed and version < SCHEMA_VERSION else None
    connection = sqlite3.connect(path, isolation_level=None, timeout=5.0)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        journal = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower()
        connection.execute("PRAGMA synchronous=FULL")
        if version < SCHEMA_VERSION:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for ddl in DDL:
                    connection.execute(ddl)
                connection.execute(f"PRAGMA application_id={APP_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED_TABLES <= tables:
            raise ValueError("state schema missing tables")
        pragma_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if pragma_version != SCHEMA_VERSION:
            raise ValueError("state schema version mismatch")
        if connection.execute("PRAGMA application_id").fetchone()[0] != APP_ID:
            raise ValueError("state application id mismatch")
        fk = connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        if journal != "wal" or not fk:
            raise ValueError("required WAL and foreign key protection missing")
        return SchemaReceipt(pragma_version, schema_sha256(), backup, journal == "wal", fk)
    finally:
        connection.close()
