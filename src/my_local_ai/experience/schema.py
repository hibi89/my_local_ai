"""MESA observation contracts: immutable, untrusted, redacted data only.

Objects here are not receipts, permissions or evidence of independent tests.
No model, provider or serialized payload can create an approved record.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_RIGHTS = frozenset({"OWNED_REDACTED", "PUBLIC_SYNTHETIC"})
_OUTCOMES = frozenset({"OBSERVED", "FAILED", "HOLD", "CANDIDATE", "NOT_RUN"})


def _valid(value: object, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class ExperienceEventV1:
    """A non-authoritative observation without raw source, prompt or secrets."""

    event_id: str
    project_id: str
    run_id: str
    task_id: str
    plan_sha256: str
    source_git_sha: str
    scope_ref: str
    rights_tag: str
    outcome: str
    error_fingerprint: str
    environment_digest: str
    observed_at: int
    evidence_stage: str = "UNTRUSTED"
    owner_approved: bool = False

    def __post_init__(self) -> None:
        for field in ("event_id", "project_id", "run_id", "task_id", "scope_ref"):
            if not _valid(getattr(self, field), _ID):
                raise ValueError("invalid experience identity")
        if (not _valid(self.plan_sha256, _SHA64)
            or not _valid(self.source_git_sha, _SHA40)
            or not _valid(self.error_fingerprint, _SHA64)
            or not _valid(self.environment_digest, _SHA64)):
            raise ValueError("invalid observation digest")
        if self.rights_tag not in _RIGHTS or self.outcome not in _OUTCOMES:
            raise ValueError("unapproved observation category")
        if type(self.observed_at) is not int or self.observed_at <= 0:
            raise ValueError("invalid observation time")
        if self.evidence_stage != "UNTRUSTED" or self.owner_approved is not False:
            raise ValueError("observations cannot self-attest or approve")

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id, "project_id": self.project_id,
            "run_id": self.run_id, "task_id": self.task_id,
            "plan_sha256": self.plan_sha256, "source_git_sha": self.source_git_sha,
            "scope_ref": self.scope_ref, "rights_tag": self.rights_tag,
            "outcome": self.outcome, "error_fingerprint": self.error_fingerprint,
            "environment_digest": self.environment_digest,
            "observed_at": self.observed_at, "evidence_stage": "UNTRUSTED",
            "owner_approved": False, "execution_allowed": False,
            "independent_f18_verified": False,
        }


@dataclass(frozen=True, slots=True)
class ExperienceSuggestionV1:
    """One advisory suggestion; no action, operator, authorization or approval."""

    strategy_ref: str
    record_ids: tuple[str, ...]
    rationale_code: str
    confidence_kind: str = "UNMEASURED"
    approved: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (not _valid(self.strategy_ref, _ID)
            or not isinstance(self.record_ids, tuple)
            or not 1 <= len(self.record_ids) <= 3
            or len(set(self.record_ids)) != len(self.record_ids)
            or any(not _valid(item, _ID) for item in self.record_ids)
            or not _valid(self.rationale_code, _ID)
            or self.confidence_kind not in {"UNMEASURED", "HEURISTIC"}
            or self.approved is not False or self.execution_allowed is not False):
            raise ValueError("invalid or privileged experience suggestion")
