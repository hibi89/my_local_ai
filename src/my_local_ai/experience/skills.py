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



@dataclass(frozen=True, slots=True)
class ShadowRollbackPlanV1:
    """An inert version-pointer proposal, not an actual file/registry rollback."""
    skill_id: str
    scope_ref: str
    revoked_content_sha256: str
    previous_content_sha256: str | None
    state: str = "SHADOW_REFERENCE_ONLY"
    owner_go: bool = False
    activated: bool = False
    code_executed: bool = False
    source_written: bool = False

    def __post_init__(self) -> None:
        if (self.state != "SHADOW_REFERENCE_ONLY"
            or not _ID.fullmatch(self.skill_id)
            or not _ID.fullmatch(self.scope_ref)
            or not _SHA64.fullmatch(self.revoked_content_sha256)
            or (self.previous_content_sha256 is not None
                and not _SHA64.fullmatch(self.previous_content_sha256))
            or any(getattr(self,n) is not False for n in (
                "owner_go","activated","code_executed","source_written",
            ))):
            raise ValueError("rollback plan cannot gain authority")


def plan_shadow_rollback(
    versions: tuple[SkillVersionV1, ...], *,
    scope_ref: str, now: int,
) -> ShadowRollbackPlanV1:
    """Resolve an exact version-parent chain to an inert previous reference.

    No code, original source, DB or skill bytes are modified. A previously
    active/approved version is NEVER recovered by this function.
    """
    if (not isinstance(versions, tuple) or not 1 <= len(versions) <= 64
        or type(now) is not int or now <= 0
        or not isinstance(scope_ref,str) or not _ID.fullmatch(scope_ref)
        or any(not isinstance(v,SkillVersionV1) for v in versions)):
        raise ValueError("invalid shadow version history")
    first=versions[0]
    if (first.version != 1 or first.parent_content_sha256 is not None
        or any(v.skill_id != first.skill_id or v.scope_ref != scope_ref
               or v.version != i+1
               or (i>0 and v.parent_content_sha256 != versions[i-1].content_sha256)
               for i,v in enumerate(versions))):
        raise ValueError("broken or cross-scope skill version chain")
    # Only an inactive tip can be considered for rollback, and the parent
    # must still be a non-expired, never-activated SHADOW reference.
    tip=versions[-1]
    if tip.state not in {"REVOKED","QUARANTINED"}:
        raise ValueError("only quarantined/revoked tip may be rolled back")
    parent=versions[-2] if len(versions)>1 else None
    previous=None
    if parent is not None and parent.state=="SHADOW" and now<parent.expiry_at:
        previous=parent.content_sha256
    return ShadowRollbackPlanV1(
        tip.skill_id,scope_ref,tip.content_sha256,previous,
    )
