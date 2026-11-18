"""MESA scoped and time-bounded retrieval; default OFF, no FTS dependency.

An unreviewed raw observation never becomes a strategy automatically.
Only explicitly curated SHADOW candidates in a new isolated MESA v2 store
can be suggested. Revocation, expiry, conflict, old v1, missing state and
corrupt databases fail back to an empty, non-authoritative suggestion set.
"""
from __future__ import annotations

import json
import sqlite3
import time

from .schema import ExperienceEventV1, ExperienceSuggestionV1
from my_local_ai.state.experience_migrations import require_experience_store

_MAX_SCAN = 64


def search_experiences(
    conn: sqlite3.Connection, *, project_id: str, plan_sha256: str,
    source_git_sha: str, scope_ref: str, rights_tag: str,
    error_fingerprint: str, enabled: bool = False, max_results: int = 3,
    now_seconds: int | None = None,
) -> tuple[ExperienceSuggestionV1, ...]:
    """Return top-three shadow hints without changing the native Controller.

    Exact SHA, rights, scope, fingerprint, and curation timing are mandatory.
    Neither a curation marker nor a suggestion is a F18 receipt/Owner grant.
    """
    if enabled is not True:
        return ()
    if type(max_results) is not int or not 1 <= max_results <= 3:
        raise ValueError("invalid MESA result bound")
    from .schema import _valid, _ID, _SHA40, _SHA64, _RIGHTS
    if (not _valid(project_id, _ID) or not _valid(scope_ref, _ID)
        or not _valid(plan_sha256, _SHA64)
        or not _valid(source_git_sha, _SHA40)
        or not _valid(error_fingerprint, _SHA64)
        or rights_tag not in _RIGHTS):
        raise ValueError("invalid MESA search scope")
    if now_seconds is None:
        now_seconds = int(time.time())
    if type(now_seconds) is not int or now_seconds <= 0:
        raise ValueError("invalid current time")
    try:
        # Old isolated MESA v1 may still be displayed but is never silently
        # migrated or trusted for reuse decisions.
        require_experience_store(conn, require_v2=True)
        rows = conn.execute(
            """SELECT e.redacted_json, c.state, c.strategy_digest,
                      c.conflict_digest, c.created_at, c.expires_at
               FROM experience_events e
               LEFT JOIN experience_curation_events c ON
                 c.sequence = (SELECT max(z.sequence)
                    FROM experience_curation_events z WHERE z.event_id=e.event_id)
               WHERE e.project_id=? AND e.plan_sha256=?
                 AND e.source_git_sha=? AND e.scope_ref=? AND e.rights_tag=?
                 AND e.error_fingerprint=?
                 AND e.outcome IN ('FAILED','HOLD','CANDIDATE')
               ORDER BY e.observed_at DESC, e.event_id DESC LIMIT ?""",
            (project_id, plan_sha256, source_git_sha, scope_ref,
             rights_tag, error_fingerprint, _MAX_SCAN + 1),
        ).fetchall()
        if len(rows) > _MAX_SCAN:
            return ()
        candidates: list[tuple[ExperienceEventV1, str, str | None]] = []
        conflicts: dict[str, set[str]] = {}
        keys = (
            "event_id", "project_id", "run_id", "task_id",
            "plan_sha256", "source_git_sha", "scope_ref", "rights_tag",
            "outcome", "error_fingerprint", "environment_digest",
            "observed_at",
        )
        for raw, state, strategy, conflict, created, expiry in rows:
            if state is None:
                continue
            if (state != "CURATION_PENDING" or type(created) is not int
                or type(expiry) is not int or now_seconds < created
                or now_seconds >= expiry):
                continue
            values = json.loads(raw)
            if not isinstance(values, dict):
                return ()
            event = ExperienceEventV1(**{k: values[k] for k in keys})
            if values != event.to_redacted_dict():
                return ()
            if (event.project_id != project_id or event.scope_ref != scope_ref
                or event.source_git_sha != source_git_sha
                or event.plan_sha256 != plan_sha256
                or event.rights_tag != rights_tag
                or event.error_fingerprint != error_fingerprint
                or not _valid(strategy, _SHA64)
                or (conflict is not None and not _valid(conflict, _SHA64))):
                return ()
            candidates.append((event, strategy, conflict))
            if conflict is not None:
                conflicts.setdefault(conflict, set()).add(strategy)
        out: list[ExperienceSuggestionV1] = []
        for event, strategy, group in candidates:
            if group is not None and len(conflicts[group]) > 1:
                continue
            out.append(ExperienceSuggestionV1(
                "strategy-" + strategy[:16], (event.event_id,),
                "CURATED_SHADOW_FINGERPRINT_MATCH",
            ))
            if len(out) >= max_results:
                break
        return tuple(out)
    except (sqlite3.Error, ValueError, TypeError, KeyError, RecursionError):
        # Optional memory failure never blocks the baseline Qwen Controller.
        return ()
