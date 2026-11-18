"""MESA local read-only status, inspected records, and redacted export.

Only an existing MESA-app-id store can be opened, never the MLA owner DB.
OS protection against a hostile concurrent writer is NOT established.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import stat

from my_local_ai.experience.retrieval import search_experiences
from my_local_ai.experience.schema import ExperienceEventV1
from my_local_ai.state.experience_migrations import require_experience_store


@contextmanager
def open_mesa_readonly(path: str | Path):
    p = Path(path)
    if ".." in p.parts:
        raise ValueError("unsafe experience path")
    p = p.absolute()
    for part in (p, *p.parents):
        info = part.lstat()
        if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0)
               & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise ValueError("unsafe experience path alias")
    metadata = p.stat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
        or metadata.st_size > 100 * 1024 * 1024):
        raise ValueError("invalid or oversized experience store")
    # Immutable, existing SQLite file: never creates DB/WAL/shm. All
    # observations are advisory; an active WAL snapshot may be stale.
    conn = sqlite3.connect(p.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=2)
    try:
        conn.execute("PRAGMA query_only=ON")
        require_experience_store(conn)
        yield conn
    finally:
        conn.close()


def _read_scoped(
    conn: sqlite3.Connection, *, project_id: str, plan_sha256: str,
    source_git_sha: str, scope_ref: str, rights_tag: str,
    event_id: str | None = None, limit: int = 100,
) -> list[dict[str, object]]:
    from my_local_ai.experience.schema import _ID, _SHA40, _SHA64, _RIGHTS, _valid
    if (not _valid(project_id, _ID) or not _valid(plan_sha256, _SHA64)
        or not _valid(source_git_sha, _SHA40)
        or not _valid(scope_ref, _ID) or rights_tag not in _RIGHTS
        or (event_id is not None and not _valid(event_id, _ID))
        or type(limit) is not int or not 1 <= limit <= 100):
        raise ValueError("invalid experience display scope")
    require_experience_store(conn)
    sql = """SELECT redacted_json FROM experience_events
             WHERE project_id=? AND plan_sha256=? AND source_git_sha=?
             AND scope_ref=? AND rights_tag=?"""
    params: list[object] = [
        project_id, plan_sha256, source_git_sha, scope_ref, rights_tag,
    ]
    if event_id is not None:
        sql += " AND event_id=?"
        params.append(event_id)
    sql += " ORDER BY observed_at DESC, event_id DESC LIMIT ?"
    params.append(limit)
    out: list[dict[str, object]] = []
    for (row,) in conn.execute(sql, params):
        blob = json.loads(row)
        if not isinstance(blob, dict):
            raise ValueError("corrupt experience")
        keys = (
            "event_id", "project_id", "run_id", "task_id",
            "plan_sha256", "source_git_sha", "scope_ref", "rights_tag",
            "outcome", "error_fingerprint", "environment_digest", "observed_at",
        )
        event = ExperienceEventV1(**{name: blob[name] for name in keys})
        if (event.project_id != project_id or event.plan_sha256 != plan_sha256
            or event.source_git_sha != source_git_sha
            or event.scope_ref != scope_ref or event.rights_tag != rights_tag):
            raise ValueError("tampered experience scope")
        # Re-serialize only safe schema properties, never raw untrusted JSON.
        out.append(event.to_redacted_dict())
    return out


def experience_read_only_view(
    conn: sqlite3.Connection, *, action: str, project_id: str,
    plan_sha256: str, source_git_sha: str, scope_ref: str,
    rights_tag: str, error_fingerprint: str | None = None,
    event_id: str | None = None,
) -> dict[str, object]:
    """Inert display data; no learn/approve/revoke/delete endpoint."""
    common = {
        "read_only": True, "execution_allowed": False,
        "owner_go": False, "independent_f18_verified": False,
        "p2": "LOCKED", "experience_stage": "UNVERIFIED_OBSERVATIONS",
    }
    if action == "search":
        if error_fingerprint is None:
            raise ValueError("search fingerprint required")
        hints = search_experiences(
            conn, project_id=project_id, plan_sha256=plan_sha256,
            source_git_sha=source_git_sha, scope_ref=scope_ref,
            rights_tag=rights_tag, error_fingerprint=error_fingerprint,
            enabled=True, max_results=3,
        )
        return {**common, "action": "search",
                "record_refs": [r.record_ids[0] for r in hints],
                "suggestion_count": len(hints), "approved": False}
    if action not in {"status", "inspect", "export-redacted"}:
        raise ValueError("unsupported MESA read-only operation")
    if action == "inspect" and event_id is None:
        raise ValueError("record identifier required")
    events = _read_scoped(
        conn, project_id=project_id, plan_sha256=plan_sha256,
        source_git_sha=source_git_sha, scope_ref=scope_ref,
        rights_tag=rights_tag, event_id=event_id,
        limit=1 if action == "inspect" else 100,
    )
    if action == "status":
        return {**common, "action": "status", "redacted_count_capped": len(events),
                "count_capped": len(events) == 100}
    return {**common, "action": action,
            "records": events, "export_raw_source": False,
            "bounded_limit": 100}



def redacted_metrics_card(
    baseline: object, assisted: object,
) -> dict[str, object]:
    """UI-facing local comparison; never a causal or certified speedup."""
    from my_local_ai.experience.evaluation import (
        TaskMetricsV1, compare_task_metrics,
    )
    if ((baseline is not None and not isinstance(baseline, TaskMetricsV1))
        or (assisted is not None and not isinstance(assisted, TaskMetricsV1))):
        raise ValueError("invalid metrics card inputs")
    return compare_task_metrics(baseline, assisted).to_redacted_dict()



def redacted_stored_metrics_card(
    conn: sqlite3.Connection, *, project_id: str, scope_ref: str,
    plan_sha256: str, source_git_sha: str,
    acceptance_sha256: str, environment_digest: str, rights_tag: str,
) -> dict[str, object]:
    """Read existing owned local observations; never compute verified savings."""
    from my_local_ai.experience.evaluation import compare_persisted_metrics
    return compare_persisted_metrics(
        conn, project_id=project_id, scope_ref=scope_ref,
        plan_sha256=plan_sha256, source_git_sha=source_git_sha,
        acceptance_sha256=acceptance_sha256,
        environment_digest=environment_digest, rights_tag=rights_tag,
    ).to_redacted_dict()
