"""MESA-only SQLite layouts. Existing MLA state and legacy MESA v1 are read-only.

v2 is provisioned ONLY for a new empty, explicitly scoped MESA store; there
is no automatic migration, no application_id takeover and no schema repair.
"""
from __future__ import annotations

import sqlite3

MESA_APP_ID = 0x4D455341
MESA_VERSION = 2
_LEGACY_VERSION = 1

_BASE_DDL = (
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

_V2_DDL = (
    """CREATE TABLE experience_curation_events (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id TEXT NOT NULL UNIQUE,
        event_id TEXT NOT NULL REFERENCES experience_events(event_id),
        state TEXT NOT NULL CHECK(state IN (
          'CURATION_PENDING','QUARANTINED','REVOKED','EXPIRED')),
        reason_code TEXT NOT NULL,
        strategy_digest TEXT NOT NULL,
        conflict_digest TEXT,
        created_at INTEGER NOT NULL CHECK(created_at > 0),
        expires_at INTEGER NOT NULL CHECK(expires_at > 0)
    )""",
    """CREATE INDEX curation_latest ON experience_curation_events
       (event_id, sequence DESC)""",
    """CREATE TRIGGER curation_no_update BEFORE UPDATE ON experience_curation_events
       BEGIN SELECT RAISE(ABORT, 'append-only curation'); END""",
    """CREATE TRIGGER curation_no_delete BEFORE DELETE ON experience_curation_events
       BEGIN SELECT RAISE(ABORT, 'append-only curation'); END""",
    """CREATE TABLE experience_metrics (
        observation_id TEXT PRIMARY KEY,
        idempotency_digest TEXT NOT NULL UNIQUE,
        project_id TEXT NOT NULL,
        scope_ref TEXT NOT NULL,
        source_git_sha TEXT NOT NULL,
        plan_sha256 TEXT NOT NULL,
        variant TEXT NOT NULL CHECK(variant IN ('BASELINE','ASSISTED')),
        redacted_json TEXT NOT NULL
    )""",
    """CREATE INDEX metrics_lookup ON experience_metrics
       (project_id, scope_ref, plan_sha256, source_git_sha, variant)""",
    """CREATE TRIGGER metrics_no_update BEFORE UPDATE ON experience_metrics
       BEGIN SELECT RAISE(ABORT, 'append-only metrics'); END""",
    """CREATE TRIGGER metrics_no_delete BEFORE DELETE ON experience_metrics
       BEGIN SELECT RAISE(ABORT, 'append-only metrics'); END""",
)
_DDL = _BASE_DDL + _V2_DDL
_V1_OBJECTS = frozenset({
    'experience_events','experience_lookup',
    'experience_no_update','experience_no_delete',
})
_V2_OBJECTS = _V1_OBJECTS | frozenset({
    'experience_curation_events','curation_latest',
    'curation_no_update','curation_no_delete',
    'experience_metrics','metrics_lookup',
    'metrics_no_update','metrics_no_delete',
})


def _schema_objects(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
    )}


def require_experience_store(
    conn: sqlite3.Connection, *, require_v2: bool = False,
) -> int:
    """Reject other app IDs and unexpected database objects; return version.

    v1 can still be inspected but is never silently promoted to v2.
    """
    if not isinstance(conn, sqlite3.Connection):
        raise ValueError("owned MESA SQLite connection required")
    app = conn.execute("PRAGMA application_id").fetchone()[0]
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    expected = {1: _V1_OBJECTS, 2: _V2_OBJECTS}.get(ver)
    if (app != MESA_APP_ID or expected is None
        or _schema_objects(conn) != expected
        or (require_v2 and ver != MESA_VERSION)):
        raise ValueError("unknown, legacy, or tampered MESA database")
    if (conn.execute("PRAGMA quick_check").fetchone()[0] != "ok"
        or conn.execute("PRAGMA foreign_key_check").fetchone() is not None):
        raise ValueError("MESA integrity check failed")
    return ver


def initialize_empty_experience_store(
    conn: sqlite3.Connection, *, explicit_new_owned_store: bool = False,
) -> None:
    """No migration of existing stores; caller must supply new owned DB."""
    if not isinstance(conn, sqlite3.Connection) or explicit_new_owned_store is not True:
        raise ValueError("MESA store initialization requires explicit scope")
    app = conn.execute("PRAGMA application_id").fetchone()[0]
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    if app or ver or _schema_objects(conn):
        raise ValueError("existing or unknown state must not be migrated")
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("PRAGMA foreign_keys=ON")
        for statement in _DDL:
            conn.execute(statement)
        conn.execute(f"PRAGMA application_id={MESA_APP_ID}")
        conn.execute(f"PRAGMA user_version={MESA_VERSION}")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    require_experience_store(conn, require_v2=True)
