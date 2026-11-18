"""Local MESA observation ingress: parsed, redacted and append-only.

No model result or caller-controlled payload can set Owner GO / F18 PASS.
Caller is responsible for providing an independently owner-approved local
MESA-only connection. This module never connects to the MLA state database.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .policy import parse_observation
from .schema import ExperienceEventV1
from my_local_ai.state.experience_migrations import require_experience_store


def _canonical(record: ExperienceEventV1) -> str:
    return json.dumps(
        record.to_redacted_dict(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True,
    )


def collect_observation(
    conn: sqlite3.Connection, raw_json: str, *,
    expected_project: str, expected_plan_sha: str,
    expected_source_sha: str, allowed_scope_refs: frozenset[str],
) -> tuple[str, bool]:
    """Persist one bounded, redacted observation; return (event ID, newly added).

    Repeated identical ingresses are idempotent. ID reuse with changed event
    contents fails closed, and append-only triggers block changes to history.
    """
    record = parse_observation(
        raw_json, expected_project=expected_project,
        expected_plan_sha=expected_plan_sha,
        expected_source_sha=expected_source_sha,
        allowed_scope_refs=allowed_scope_refs,
    )
    require_experience_store(conn)
    encoded = _canonical(record)
    # Idempotency uses ownership, request and source context, never raw data.
    identity = "|".join((
        record.project_id, record.run_id, record.task_id,
        record.event_id, record.source_git_sha,
    ))
    identity_key = hashlib.sha256(identity.encode("ascii")).hexdigest()
    with conn:
        # One SQL statement resolves the duplicate-insert race. OR IGNORE
        # cannot edit an existing row and we check the *entire* canonical
        # record before accepting any replay. Other unique-key collisions
        # (or changed contents) are explicit failures.
        inserted = conn.execute(
            """INSERT OR IGNORE INTO experience_events
               (event_id, idempotency_key, project_id, run_id, task_id,
                plan_sha256, source_git_sha, scope_ref, rights_tag, outcome,
                error_fingerprint, environment_digest, observed_at, redacted_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record.event_id, identity_key, record.project_id,
             record.run_id, record.task_id, record.plan_sha256,
             record.source_git_sha, record.scope_ref, record.rights_tag,
             record.outcome, record.error_fingerprint,
             record.environment_digest, record.observed_at, encoded),
        )
        existing = conn.execute(
            "SELECT idempotency_key, redacted_json FROM experience_events WHERE event_id=?",
            (record.event_id,),
        ).fetchone()
        if existing != (identity_key, encoded):
            raise ValueError("conflicting observation or identity collision")
        if inserted.rowcount not in (0, 1):
            raise ValueError("unexpected observation insertion result")
        return (record.event_id, inserted.rowcount == 1)

def count_owned_observations(
    conn: sqlite3.Connection, *, project_id: str, scope_ref: str,
    source_git_sha: str,
) -> int:
    require_experience_store(conn)
    from .schema import _valid, _ID, _SHA40
    if (not _valid(project_id, _ID)
        or not _valid(scope_ref, _ID)
        or not _valid(source_git_sha, _SHA40)):
        raise ValueError("invalid scoped observation count")
    return int(conn.execute(
        """SELECT count(*) FROM experience_events
         WHERE project_id=? AND scope_ref=? AND source_git_sha=?""",
        (project_id, scope_ref, source_git_sha),
    ).fetchone()[0])
