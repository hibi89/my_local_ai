"""V2 Evidence Gate: non-authoritative, immutable advice-only reuse checks.

The gate does not mint, rebind, or authenticate F18 receipts, owner consent,
run leases, Git permissions or verification results. Its trusted receipt
resolver must be supplied by a separately protected caller; absent one, HOLD.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Callable

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_RIGHTS = frozenset({"OWNED_REDACTED", "PUBLIC_SYNTHETIC"})
_EFFECTS = frozenset({"NO_EFFECT", "STATIC_READ", "READ_ONLY_ANALYSIS"})
_STATES = frozenset({"REUSABLE_ADVICE", "REVALIDATION_REQUIRED", "UNKNOWN", "REVOKED"})
_RECORD_STATES = frozenset({"ACTIVE", "REVOKED", "QUARANTINED", "EXPIRED"})


def _match(value: object, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class EvidenceQueryV1:
    project_id: str
    plan_sha256: str
    source_git_sha: str
    dependency_fingerprint: str
    input_contract_digest: str
    output_contract_digest: str
    scanner_rules_sha256: str
    environment_fingerprint: str
    rights_tag: str
    scope_ref: str
    desired_effects: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not _match(self.project_id, _ID)
            or not _match(self.plan_sha256, _SHA64)
            or not _match(self.source_git_sha, _SHA40)
            or not _match(self.scope_ref, _ID)
            or any(not _match(getattr(self, name), _SHA64) for name in (
                "dependency_fingerprint", "input_contract_digest",
                "output_contract_digest", "scanner_rules_sha256",
                "environment_fingerprint",
            )) or self.rights_tag not in _RIGHTS
            or not isinstance(self.desired_effects, tuple)
            or len(self.desired_effects) > 8
            or len(set(self.desired_effects)) != len(self.desired_effects)
            or any(e not in _EFFECTS for e in self.desired_effects)):
            raise ValueError("invalid non-executing evidence query")


@dataclass(frozen=True, slots=True)
class EvidenceRecordV1:
    """Reference to prior evidence; the record itself is NOT an attestation."""
    evidence_ref: str
    issuer_ref: str
    project_id: str
    plan_sha256: str
    source_git_sha: str
    dependency_fingerprint: str
    input_contract_digest: str
    output_contract_digest: str
    scanner_rules_sha256: str
    environment_fingerprint: str
    rights_tag: str
    scope_ref: str
    allowed_effects: tuple[str, ...]
    state: str
    expires_at: int

    def __post_init__(self) -> None:
        if (not _match(self.evidence_ref, _ID)
            or not _match(self.issuer_ref, _ID)
            or self.state not in _RECORD_STATES
            or type(self.expires_at) is not int or self.expires_at <= 0):
            raise ValueError("invalid evidence reference")
        # The record is an untrusted reference regardless of caller claims.
        EvidenceQueryV1(
            self.project_id, self.plan_sha256, self.source_git_sha,
            self.dependency_fingerprint, self.input_contract_digest,
            self.output_contract_digest, self.scanner_rules_sha256,
            self.environment_fingerprint, self.rights_tag, self.scope_ref,
            self.allowed_effects,
        )


@dataclass(frozen=True, slots=True)
class EvidenceDecisionV1:
    state: str
    candidate_refs: tuple[str, ...]
    compatibility_reasons: tuple[str, ...]
    invalidations: tuple[str, ...]
    revalidation_tasks: tuple[str, ...]
    checked_at: int
    decision_digest: str
    permitted_use: str = "ADVICE_ONLY"
    can_execute: bool = False
    owner_go: bool = False
    independent_f18_verified: bool = False
    receipt_reissued: bool = False

    def __post_init__(self) -> None:
        if (self.state not in _STATES
            or self.permitted_use != "ADVICE_ONLY"
            or any(getattr(self, field) is not False for field in (
                "can_execute", "owner_go", "independent_f18_verified",
                "receipt_reissued",
            ))):
            raise ValueError("evidence verdict cannot grant authority")


def decide_evidence(
    query: EvidenceQueryV1,
    record: EvidenceRecordV1 | None, *,
    checked_at: int,
    trusted_receipt_check: Callable[[str, str], bool] | None = None,
) -> EvidenceDecisionV1:
    """Compare SHA/scope/version facts; return advice, never a PASS receipt.

    trusted_receipt_check(ref, issuer) MUST reside in an OS-protected verifier
    boundary. A model/Controller callback is insufficient for trusted execution,
    and success here can never substitute for that boundary.
    """
    if not isinstance(query, EvidenceQueryV1) or type(checked_at) is not int or checked_at <= 0:
        raise ValueError("invalid gate input")

    reasons: list[str] = []
    invalid: list[str] = []
    revisit: list[str] = []
    state = "UNKNOWN"
    refs: tuple[str, ...] = ()

    if record is None:
        reasons.append("NO_CANDIDATE")
    elif not isinstance(record, EvidenceRecordV1):
        raise ValueError("invalid candidate type")
    else:
        # A previously revoked/quarantined/expired record stays unusable,
        # regardless of matching digests or any callback.
        if record.state != "ACTIVE" or checked_at >= record.expires_at:
            state = "REVOKED"
            invalid.append("CANDIDATE_INACTIVE")
        elif (query.project_id != record.project_id
              or query.rights_tag != record.rights_tag
              or query.scope_ref != record.scope_ref):
            invalid.append("RIGHTS_OR_SCOPE_MISMATCH")
        elif not set(query.desired_effects).issubset(record.allowed_effects):
            invalid.append("EFFECTS_MISMATCH")
        else:
            for name, reason in (
                ("plan_sha256", "PLAN_CHANGED"),
                ("source_git_sha", "SOURCE_CHANGED"),
                ("dependency_fingerprint", "DEPENDENCIES_CHANGED"),
                ("input_contract_digest", "INPUT_CHANGED"),
                ("output_contract_digest", "OUTPUT_CHANGED"),
                ("scanner_rules_sha256", "RULES_CHANGED"),
                ("environment_fingerprint", "ENVIRONMENT_CHANGED"),
            ):
                if getattr(query, name) != getattr(record, name):
                    invalid.append(reason)
            if invalid:
                state = "REVALIDATION_REQUIRED"
                revisit.append("RECHECK_EXACT_SOURCE_AND_DEPENDENCIES")
            elif trusted_receipt_check is None:
                reasons.append("PROTECTED_RECEIPT_CHECK_UNAVAILABLE")
            else:
                # Any verifier error also fails shut; never trust a signed
                # assertion embedded in the candidate record itself.
                try:
                    verified = trusted_receipt_check(record.evidence_ref, record.issuer_ref)
                except Exception:
                    verified = False
                if verified is True:
                    state = "REUSABLE_ADVICE"
                    refs = (record.evidence_ref,)
                    reasons.append("REFERENCE_COMPATIBLE_FOR_ADVICE_ONLY")
                else:
                    reasons.append("RECEIPT_NOT_AUTHENTICATED")

    payload = {
        "state": state, "candidate_refs": refs, "reasons": reasons,
        "invalidations": invalid, "revalidation_tasks": revisit,
        "checked_at": checked_at, "permitted_use": "ADVICE_ONLY",
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return EvidenceDecisionV1(
        state, refs, tuple(reasons), tuple(invalid), tuple(revisit),
        checked_at, fingerprint,
    )
