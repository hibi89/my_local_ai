"""MESA-owned SQLite v1 schema, isolated from MLA's protected state store.

This module does not migrate existing MLA DBs, modify ACLs, or authorize use
of customer data. Only an empty approved MESA store can be initialized.
"""
from __future__ import annotations

import sqlite3

MESA_APP_ID = 0x4D455341
MESA_VERSION = 1

_DDL = (
    """CREATE TABLE experience_events (
        event_id TEXT PRIMARY KEY,
        idempotency_key TEXT NOT NULL UNIQUE,
        project_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        plan_sha256 TEXT NOT NULL,
        source_git_sha TEXT NOT NULL,
        scope_ref TEXT NOT NULL,
        rights_tag TEXT NOT NULL,
        outcome TEXT NOT NULL,
        error_fingerprint TEXT NOT NULL,
        environment_digest TEXT NOT NULL,
        observed_at INTEGER NOT NULL,
        redacted_json TEXT NOT NULL
    )""",
    """CREATE INDEX experience_lookup ON experience_events
       (project_id, scope_ref, source_git_sha, error_fingerprint, observed_at DESC)""",
    """CREATE TRIGGER experience_no_update BEFORE UPDATE ON experience_events
       BEGIN SELECT RAISE(ABORT, 'append-only experience'); END""",
    """CREATE TRIGGER experience_no_delete BEFORE DELETE ON experience_events
       BEGIN SELECT RAISE(ABORT, 'append-only experience'); END""",
)


def _schema_objects(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
    )}


def require_experience_store(conn: sqlite3.Connection) -> None:
    if not isinstance(conn, sqlite3.Connection):
        raise ValueError("owned MESA SQLite connection required")
    app = conn.execute("PRAGMA application_id").fetchone()[0]
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    expected = {
        "experience_events", "experience_lookup",
        "experience_no_update", "experience_no_delete",
    }
    if app != MESA_APP_ID or ver != MESA_VERSION or _schema_objects(conn) != expected:
        raise ValueError("unknown or tampered MESA database")
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("MESA integrity check failed")


def initialize_empty_experience_store(
    conn: sqlite3.Connection, *, explicit_new_owned_store: bool = False,
) -> None:
    """Never upgrade/overwrite existing state. Database creation needs owner scope.

    A caller must create an isolated, new, owned database and pass an explicit
    scope opt-in. This Boolean is not an Owner signer or runtime GO.
    """
    if not isinstance(conn, sqlite3.Connection) or explicit_new_owned_store is not True:
        raise ValueError("MESA store initialization requires explicit scope")
    app = conn.execute("PRAGMA application_id").fetchone()[0]
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    if app or ver or _schema_objects(conn):
        raise ValueError("existing or unknown state must not be migrated")
    try:
        conn.execute("BEGIN IMMEDIATE")
        for statement in _DDL:
            conn.execute(statement)
        conn.execute(f"PRAGMA application_id={MESA_APP_ID}")
        conn.execute(f"PRAGMA user_version={MESA_VERSION}")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    require_experience_store(conn)
