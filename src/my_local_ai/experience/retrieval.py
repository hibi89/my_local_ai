"""MESA indexed local fingerprint retrieval; optional, default OFF.

Search is scoped to exact owned project, branch source, plan and rights.
Returns at most three non-executable hints. No SQL FTS5 required: deterministic
indexed fallback works on Python's standard sqlite3 distribution.
"""
from __future__ import annotations

import json
import sqlite3

from .schema import ExperienceEventV1, ExperienceSuggestionV1
from my_local_ai.state.experience_migrations import require_experience_store


def search_experiences(
    conn: sqlite3.Connection, *, project_id: str, plan_sha256: str,
    source_git_sha: str, scope_ref: str, rights_tag: str,
    error_fingerprint: str, enabled: bool = False, max_results: int = 3,
) -> tuple[ExperienceSuggestionV1, ...]:
    """Read only indexed, redacted observations, never blindly use a skill.

    The caller must pass exact live context, not context copied from the
    candidate record. A project switch, SHA drift or disabled MESA returns
    no suggestions. Untrusted evidence is never upgraded by retrieval.
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
    try:
        require_experience_store(conn)
        rows = conn.execute(
            """SELECT redacted_json FROM experience_events
               WHERE project_id=? AND plan_sha256=? AND source_git_sha=?
                 AND scope_ref=? AND rights_tag=? AND error_fingerprint=?
                 AND outcome IN ('FAILED','HOLD','OBSERVED')
               ORDER BY observed_at DESC, event_id DESC LIMIT ?""",
            (project_id, plan_sha256, source_git_sha, scope_ref,
             rights_tag, error_fingerprint, max_results),
        ).fetchall()
        suggestions: list[ExperienceSuggestionV1] = []
        for (raw,) in rows:
            values = json.loads(raw)
            if not isinstance(values, dict):
                return ()
            # DB can hold only the old non-privileged events, and stored
            # display fields must not be mistaken for independent evidence.
            record = ExperienceEventV1(
                **{key: values[key] for key in (
                    "event_id", "project_id", "run_id", "task_id",
                    "plan_sha256", "source_git_sha", "scope_ref", "rights_tag",
                    "outcome", "error_fingerprint", "environment_digest",
                    "observed_at",
                )}
            )
            if (record.project_id != project_id or record.scope_ref != scope_ref
                or record.source_git_sha != source_git_sha
                or record.plan_sha256 != plan_sha256
                or record.rights_tag != rights_tag
                or record.error_fingerprint != error_fingerprint):
                return ()
            suggestions.append(ExperienceSuggestionV1(
                "strategy-" + record.error_fingerprint[:16],
                (record.event_id,), "FINGERPRINT_MATCH_UNVERIFIED",
            ))
        return tuple(suggestions)
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        # Corrupt optional memory is never allowed to block the main model.
        return ()
