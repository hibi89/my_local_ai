"""AXZERO optional read-only capability preflight, no runtime authority.

AXZERO is a separate product. No import, network call, CLI execution, package
loading, generated code execution, original file writes or model calls occur.
Absent or unsafe metadata leaves the existing local Qwen Controller untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_EFFECTS = frozenset({"NO_EFFECT", "STATIC_READ", "READ_ONLY_ANALYSIS"})
_MAX_CAP_BYTES = 8192


def _valid(value: object, regex: re.Pattern[str]) -> bool:
    return isinstance(value, str) and regex.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class CapabilityQueryV1:
    request_id: str
    task_type: str
    input_contract_digest: str
    environment_fingerprint: str
    proposed_effects: tuple[str, ...]
    source_git_sha: str
    scope_ref: str
    max_cost_usd: int = 0
    max_calls: int = 1

    def __post_init__(self):
        if (not _valid(self.request_id,_ID)
            or not _valid(self.task_type,_ID)
            or not _valid(self.scope_ref,_ID)
            or not _valid(self.input_contract_digest,_SHA64)
            or not _valid(self.environment_fingerprint,_SHA64)
            or not _valid(self.source_git_sha,_SHA40)
            or not isinstance(self.proposed_effects,tuple)
            or len(self.proposed_effects)>8
            or len(set(self.proposed_effects))!=len(self.proposed_effects)
            or any(e not in _EFFECTS for e in self.proposed_effects)
            or type(self.max_cost_usd) is not int or self.max_cost_usd!=0
            or type(self.max_calls) is not int or not 1<=self.max_calls<=8):
            raise ValueError("invalid bounded AXZERO capability query")


@dataclass(frozen=True, slots=True)
class CapabilityDecisionV1:
    decision: str
    reason: str
    capability_id: str | None = None
    artifact_sha256: str | None = None
    policy_sha256: str | None = None
    evidence_ref: str | None = None
    evidence_sha256: str | None = None
    selected_provider: str = "LOCAL_QWEN_CANDIDATE_ONLY"
    actual_model_calls: int = 0
    execution_allowed: bool = False
    owner_go_verified: bool = False
    f18_verified: bool = False
    git_write_allowed: bool = False

    def __post_init__(self):
        if (self.decision not in {"REQUEST_MODEL","REQUIRE_APPROVAL","BLOCK"}
            or (self.evidence_sha256 is not None
                and not _valid(self.evidence_sha256, _SHA64))
            or self.selected_provider != "LOCAL_QWEN_CANDIDATE_ONLY"
            or type(self.actual_model_calls) is not int or self.actual_model_calls!=0
            or any(getattr(self,n) is not False for n in (
                "execution_allowed","owner_go_verified","f18_verified",
                "git_write_allowed"))):
            raise ValueError("AXZERO preflight cannot grant runtime authority")


def _unique_pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise ValueError("duplicate capability JSON key")
        out[k]=v
    return out


def inspect_axzero_capability(
    query: CapabilityQueryV1, *, catalog_json: str | None,
    pinned_artifact_sha256: str | None = None,
    pinned_policy_sha256: str | None = None,
    pinned_evidence_sha256: str | None = None,
) -> CapabilityDecisionV1:
    """Inspect *data only*. A pin is not a signature or reviewer receipt.

    Even an exact schema+SHA match requires a protected Controller decision
    and independently approved Typed Operator before any future execution.
    """
    if not isinstance(query,CapabilityQueryV1):
        raise ValueError("typed AXZERO query required")
    if catalog_json is None:
        return CapabilityDecisionV1("REQUEST_MODEL","AXZERO_OFF_FALLBACK")
    if (not isinstance(catalog_json,str)
        or len(catalog_json.encode("utf-8"))>_MAX_CAP_BYTES
        or not _valid(pinned_artifact_sha256,_SHA64)
        or not _valid(pinned_policy_sha256,_SHA64)
        or not _valid(pinned_evidence_sha256,_SHA64)):
        return CapabilityDecisionV1("REQUEST_MODEL","MISSING_PINNED_CAPABILITY")
    try:
        data=json.loads(
            catalog_json,object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        expected={
            "version","origin","capability_id","task_type",
            "artifact_sha256","policy_sha256","evidence_ref",
            "evidence_sha256",
            "input_contract_digest","environment_fingerprint",
            "allowed_effects","source_git_sha","scope_ref",
            "approved_for_execution",
        }
        if (not isinstance(data,dict) or set(data)!=expected
            or type(data["version"]) is not int or data["version"]!=1
            or data["origin"]!="AXZERO_READ_ONLY_CAPABILITY"
            or data["approved_for_execution"] is not False
            or not _valid(data["capability_id"],_ID)
            or not _valid(data["evidence_ref"],_ID)
            or not _valid(data["artifact_sha256"],_SHA64)
            or not _valid(data["policy_sha256"],_SHA64)
            or not _valid(data["evidence_sha256"],_SHA64)
            or not isinstance(data["allowed_effects"],list)
            or len(data["allowed_effects"])>8
            or len(set(data["allowed_effects"]))!=len(data["allowed_effects"])
            or any(not isinstance(e,str) or e not in _EFFECTS
                   for e in data["allowed_effects"])):
            raise ValueError("unrecognized capability contract")
    except (TypeError,ValueError,UnicodeError,RecursionError):
        return CapabilityDecisionV1("REQUEST_MODEL","INVALID_CAPABILITY_FALLBACK")
    if (data["artifact_sha256"]!=pinned_artifact_sha256
        or data["policy_sha256"]!=pinned_policy_sha256
        or data["evidence_sha256"]!=pinned_evidence_sha256
        or data["task_type"]!=query.task_type
        or data["input_contract_digest"]!=query.input_contract_digest
        or data["environment_fingerprint"]!=query.environment_fingerprint
        or data["source_git_sha"]!=query.source_git_sha
        or data["scope_ref"]!=query.scope_ref
        or not set(query.proposed_effects).issubset(data["allowed_effects"])):
        return CapabilityDecisionV1("REQUEST_MODEL","CAPABILITY_SCOPE_OR_HASH_MISMATCH")
    return CapabilityDecisionV1(
        "REQUIRE_APPROVAL","PIN_MATCH_STILL_NOT_TRUSTED",
        data["capability_id"],data["artifact_sha256"],data["policy_sha256"],
        data["evidence_ref"],data["evidence_sha256"],
    )


def preflight_controller_axzero(
    *, plan_json: str, states: dict[str,str], task_id: str,
    query: CapabilityQueryV1, catalog_json: str | None,
    pinned_artifact_sha256: str | None = None,
    pinned_policy_sha256: str | None = None,
    pinned_evidence_sha256: str | None = None,
) -> CapabilityDecisionV1:
    """Controller's native READY remains the first authority boundary."""
    from my_local_ai.contracts.plan import PlanSpec
    from my_local_ai.controller.decision import Controller
    plan=PlanSpec.parse_json(plan_json)
    ready=Controller(plan).propose(states,independently_verified=())
    if (ready.execution_allowed or ready.owner_go or ready.verified
        or query.source_git_sha!=plan.blueprint_sha
        or not isinstance(task_id,str)):
        return CapabilityDecisionV1("BLOCK","PLAN_OR_SOURCE_MISMATCH")
    if task_id not in {d.task_id for d in ready.decisions}:
        return CapabilityDecisionV1("BLOCK","NOT_NATIVE_READY")
    return inspect_axzero_capability(
        query,catalog_json=catalog_json,
        pinned_artifact_sha256=pinned_artifact_sha256,
        pinned_policy_sha256=pinned_policy_sha256,
        pinned_evidence_sha256=pinned_evidence_sha256,
    )
