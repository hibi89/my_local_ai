"""Versioned, additive SQLite schema for local My Local AI state.

Untrusted plan/receipt data cannot create a VERIFIED record by schema default.
"""
from __future__ import annotations

import hashlib

APP_ID = 0x4D4C4131  # MLA1; refuse databases with a different ownership marker
SCHEMA_VERSION = 1

DDL = (
    """CREATE TABLE plans (
      plan_id TEXT PRIMARY KEY,
      plan_sha TEXT NOT NULL UNIQUE,
      blueprint_sha TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'AWAITING_OWNER'
        CHECK (state IN ('AWAITING_OWNER','APPROVED','HOLD','STOPPED')),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE tasks (
      plan_id TEXT NOT NULL,
      task_id TEXT NOT NULL,
      source_sha TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'QUEUED'
        CHECK (state IN ('QUEUED','READY','LEASED','CODING','REVIEW_PENDING','REPAIR_ONCE','HOLD','BLOCKED_DEPENDENCY','AWAITING_OWNER','INTERRUPTED','VERIFIED')),
      PRIMARY KEY (plan_id, task_id),
      FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE RESTRICT
    )""",
    """CREATE TABLE runs (
      run_id TEXT PRIMARY KEY,
      plan_id TEXT NOT NULL,
      task_id TEXT NOT NULL,
      baseline_sha TEXT NOT NULL,
      lease_epoch INTEGER NOT NULL CHECK (lease_epoch > 0),
      state TEXT NOT NULL DEFAULT 'REVIEW_PENDING',
      candidate_sha TEXT,
      UNIQUE (plan_id, task_id, baseline_sha, lease_epoch),
      FOREIGN KEY (plan_id, task_id) REFERENCES tasks(plan_id, task_id) ON DELETE RESTRICT
    )""",
    """CREATE TABLE leases (
      plan_id TEXT NOT NULL,
      task_id TEXT NOT NULL,
      generation INTEGER NOT NULL CHECK (generation > 0),
      run_id TEXT NOT NULL,
      PRIMARY KEY (plan_id, task_id),
      FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE RESTRICT
    )""",
    """CREATE TABLE attempts (
      run_id TEXT NOT NULL,
      attempt_number INTEGER NOT NULL CHECK (attempt_number IN (1,2)),
      state TEXT NOT NULL,
      PRIMARY KEY (run_id, attempt_number),
      FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE RESTRICT
    )""",
    """CREATE TABLE reviews (
      review_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      candidate_sha TEXT NOT NULL,
      result TEXT NOT NULL DEFAULT 'UNTRUSTED'
        CHECK (result IN ('UNTRUSTED','HOLD','REJECTED','TRUSTED_PASS')),
      trusted_boundary_id TEXT,
      reviewer_sha TEXT,
      FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE RESTRICT
    )""",
    """CREATE TABLE integrations (
      integration_id TEXT PRIMARY KEY,
      review_id TEXT NOT NULL UNIQUE,
      local_ref TEXT NOT NULL,
      integrated_sha TEXT NOT NULL,
      FOREIGN KEY (review_id) REFERENCES reviews(review_id) ON DELETE RESTRICT
    )""",
    """CREATE TABLE events (
      event_id INTEGER PRIMARY KEY AUTOINCREMENT,
      plan_id TEXT,
      event_kind TEXT NOT NULL,
      event_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      safe_summary TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE RESTRICT
    )""",
    """CREATE TABLE owner_consents (
      consent_id TEXT PRIMARY KEY,
      plan_sha TEXT NOT NULL,
      scope TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'NOT_APPROVED'
        CHECK (state IN ('NOT_APPROVED','APPROVED','REVOKED')),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
)
REQUIRED_TABLES = frozenset({
    "plans", "tasks", "runs", "leases", "attempts", "reviews",
    "integrations", "events", "owner_consents"
})

def canonical_schema_sql() -> dict[str, str]:
    """Normalized v1 CREATE TABLE text to reject drift and unknown objects.

    Only whitespace is normalized; altered constraints are NOT equivalent.
    """
    return {
        statement.split("(", 1)[0].split()[-1]: " ".join(statement.split())
        for statement in DDL
    }


def schema_sha256() -> str:
    return hashlib.sha256(("\n".join(DDL) + "\nversion=1").encode("utf-8")).hexdigest()
