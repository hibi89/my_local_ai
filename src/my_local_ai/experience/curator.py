"""MESA deterministic failure classification and contamination quarantine.

This is a shadow-mode curator. A guest or an AI-suggested root cause cannot
promote a skill, issue trusted evidence or grant an action. No model runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from .schema import ExperienceEventV1

_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_STATES = frozenset({"CURATION_PENDING", "QUARANTINED", "REVOKED", "EXPIRED"})


@dataclass(frozen=True, slots=True)
class CurationResult:
    event_id: str
    strategy_digest: str
    state: str
    reason_codes: tuple[str, ...]
    proposed_action_digest: str
    owner_approved: bool = False
    verified: bool = False
    may_run: bool = False

    def __post_init__(self) -> None:
        if (self.state not in _STATES
            or any(getattr(self, f) is not False for f in
                   ("owner_approved", "verified", "may_run"))):
            raise ValueError("untrusted curation must not grant authority")


def classify_experience(
    event: ExperienceEventV1, *, strategy_digest: str,
    proposed_action_digest: str, expected_source_sha: str,
    expected_scope: str, now: int, expires_at: int,
    revoked_event_ids: frozenset[str] = frozenset(),
    suspicious_digest_ids: frozenset[str] = frozenset(),
) -> CurationResult:
    """Curate an owned, redacted failure without enabling a skill.

    Decision output is always non-authoritative. Separate protected review
    and owner approval are required before any future ACTIVE transition.
    """
    if (not isinstance(event, ExperienceEventV1)
        or not isinstance(strategy_digest, str)
        or _SHA64.fullmatch(strategy_digest) is None
        or not isinstance(proposed_action_digest, str)
        or _SHA64.fullmatch(proposed_action_digest) is None
        or not isinstance(expected_source_sha, str)
        or not isinstance(expected_scope, str)
        or type(now) is not int or now <= 0
        or type(expires_at) is not int or expires_at <= event.observed_at
        or not isinstance(revoked_event_ids, frozenset)
        or not isinstance(suspicious_digest_ids, frozenset)):
        raise ValueError("invalid curation request")
    if event.event_id in revoked_event_ids:
        state, reasons = "REVOKED", ("EXPLICIT_REVOCATION",)
    elif now >= expires_at:
        state, reasons = "EXPIRED", ("REVALIDATION_REQUIRED",)
    elif (event.source_git_sha != expected_source_sha
          or event.scope_ref != expected_scope
          or strategy_digest in suspicious_digest_ids):
        state, reasons = "QUARANTINED", ("SOURCE_SCOPE_OR_POISONING",)
    elif event.outcome not in {"FAILED", "HOLD", "CANDIDATE"}:
        state, reasons = "QUARANTINED", ("NO_FAILURE_OR_CANDIDATE",)
    else:
        state, reasons = "CURATION_PENDING", ("UNVERIFIED_SHADOW_CANDIDATE",)
    return CurationResult(
        event.event_id, strategy_digest, state, reasons, proposed_action_digest,
    )


def candidate_fingerprint(event: ExperienceEventV1, *, strategy_digest: str) -> str:
    if not isinstance(event, ExperienceEventV1) or not isinstance(strategy_digest, str) or _SHA64.fullmatch(strategy_digest) is None:
        raise ValueError("invalid candidate")
    return hashlib.sha256(
        ("mesa-candidate-v1|" + event.project_id + "|" + event.event_id + "|"
         + event.plan_sha256 + "|" + event.source_git_sha + "|"
         + strategy_digest).encode("ascii")
    ).hexdigest()


def append_curation_decision(
    conn: "sqlite3.Connection", *, decision_id: str,
    result: CurationResult, created_at: int, expires_at: int,
    expected_project: str, expected_source_sha: str, expected_scope: str,
    conflict_digest: str | None = None,
) -> bool:
    """Persist a *non-authoritative* append-only shadow/quarantine decision.

    Returns False for identical replay. A stale or mismatched event, earlier
    timestamp, altered replay or any attempt at an ACTIVE grant fails closed.
    No untrusted text, skill content, OS access or signed PASS is stored.
    """
    import sqlite3
    import json
    from my_local_ai.state.experience_migrations import require_experience_store
    from .schema import _ID, _valid
    if (not isinstance(result, CurationResult)
        or not _valid(decision_id, _ID)
        or not _valid(expected_project, _ID)
        or not _valid(expected_scope, _ID)
        or not isinstance(expected_source_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", expected_source_sha) is None
        or type(created_at) is not int or created_at <= 0
        or type(expires_at) is not int or expires_at <= created_at
        or (conflict_digest is not None
            and (not isinstance(conflict_digest, str)
                 or _SHA64.fullmatch(conflict_digest) is None))
        or result.state not in _STATES):
        raise ValueError("invalid curation persistence request")
    require_experience_store(conn, require_v2=True)
    with conn:
        raw = conn.execute(
            """SELECT redacted_json FROM experience_events WHERE
               event_id=? AND project_id=? AND source_git_sha=? AND scope_ref=?""",
            (result.event_id, expected_project, expected_source_sha, expected_scope),
        ).fetchone()
        if raw is None:
            raise ValueError("curation event not in protected scope")
        payload = json.loads(raw[0])
        if (payload.get("evidence_stage") != "UNTRUSTED"
            or payload.get("owner_approved") is not False):
            raise ValueError("untrusted curation source")
        latest = conn.execute(
            """SELECT created_at FROM experience_curation_events
               WHERE event_id=? ORDER BY sequence DESC LIMIT 1""",
            (result.event_id,),
        ).fetchone()
        fields = (result.event_id, result.state, result.reason_codes[0],
                  result.strategy_digest, conflict_digest, created_at, expires_at)
        old = conn.execute(
            """SELECT event_id,state,reason_code,strategy_digest,
                      conflict_digest,created_at,expires_at
               FROM experience_curation_events WHERE decision_id=?""",
            (decision_id,),
        ).fetchone()
        if old is not None:
            if old != fields:
                raise ValueError("curation decision ID replay mismatch")
            return False
        if latest is not None and created_at < latest[0]:
            raise ValueError("backdated curation decision")
        conn.execute(
            """INSERT INTO experience_curation_events
               (decision_id,event_id,state,reason_code,strategy_digest,
                conflict_digest,created_at,expires_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (decision_id, *fields),
        )
    return True
