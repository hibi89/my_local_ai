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
