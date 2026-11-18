"""Versioned MESA skill metadata; never runs untrusted skill content.

A skill version is an inert reference to a digest. Actual skill bytes,
execution, promotion, rollback and signed owner approval are out-of-band.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class SkillVersionV1:
    skill_id: str
    version: int
    content_sha256: str
    parent_content_sha256: str | None
    scope_ref: str
    expiry_at: int
    state: str = "SHADOW"

    def __post_init__(self) -> None:
        if (not isinstance(self.skill_id, str)
            or _ID.fullmatch(self.skill_id) is None
            or not isinstance(self.scope_ref, str)
            or _ID.fullmatch(self.scope_ref) is None
            or type(self.version) is not int or self.version < 1
            or not isinstance(self.content_sha256, str)
            or _SHA64.fullmatch(self.content_sha256) is None
            or (self.parent_content_sha256 is not None
                and (not isinstance(self.parent_content_sha256, str)
                     or _SHA64.fullmatch(self.parent_content_sha256) is None))
            or type(self.expiry_at) is not int or self.expiry_at <= 0
            or self.state not in {"SHADOW", "REVOKED", "QUARANTINED"}):
            raise ValueError("invalid inert skill version")


@dataclass(frozen=True, slots=True)
class SkillAdvice:
    skill_id: str
    content_sha256: str
    scope_ref: str
    status: str
    execution_allowed: bool = False
    owner_approved: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed is not False or self.owner_approved is not False:
            raise ValueError("skills cannot approve themselves")


def inspect_skill(
    skill: SkillVersionV1, *, scope_ref: str, now: int,
    content_sha256: str,
) -> SkillAdvice:
    if not isinstance(skill, SkillVersionV1) or type(now) is not int or now <= 0:
        raise ValueError("invalid skill inquiry")
    eligible = (
        skill.state == "SHADOW" and scope_ref == skill.scope_ref
        and now < skill.expiry_at and content_sha256 == skill.content_sha256
    )
    return SkillAdvice(
        skill.skill_id, skill.content_sha256, skill.scope_ref,
        "SHADOW_ADVICE_ONLY" if eligible else "QUARANTINED_OR_STALE",
    )
