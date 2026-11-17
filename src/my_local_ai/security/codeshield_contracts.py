"""CodeShield V1.3 immutable, non-executing security decision contracts.

All fields are bounded metadata, not OS/Git attestations. Scanner/model input
can never mint owner consent, F18 trust, execution permission or promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}\Z")
_TOOLS = frozenset({"ruff", "semgrep", "gitleaks", "osv", "defender"})
_FORBIDDEN = frozenset({".git", ".gitattributes", ".gitmodules", ".gitignore",
                       ".env", ".ssh", ".aws", ".npmrc", ".pypirc"})


class CodeShieldHold(ValueError):
    """Invalid policy/evidence; does not grant any access."""

    def __init__(self, reason: str = "INVALID_CONTRACT"):
        self.code = reason if reason in {
            "INVALID_CONTRACT", "UNSAFE_PATH", "UNPINNED_SCANNER",
            "STALE_EVIDENCE", "UNTRUSTED_DECISION",
        } else "INVALID_CONTRACT"
        super().__init__(self.code)


class RiskOutcome(str, Enum):
    ALLOW_NON_EXECUTING = "ALLOW_NON_EXECUTING"
    REQUIRES_ISOLATION_HOLD = "REQUIRES_ISOLATION_HOLD"
    HOLD_HIGH_RISK = "HOLD_HIGH_RISK"
    UNKNOWN_HOLD = "UNKNOWN_HOLD"


class DataClass(str, Enum):
    PUBLIC_SYNTHETIC = "PUBLIC_SYNTHETIC"
    LOCAL_PRIVATE = "LOCAL_PRIVATE"
    OWNER_PROTECTED = "OWNER_PROTECTED"
    CUSTOMER_SECRET = "CUSTOMER_SECRET"


class ActionKind(str, Enum):
    STATIC_READ = "STATIC_READ"
    UNTRUSTED_EXECUTION = "UNTRUSTED_EXECUTION"
    PROTECTED_MUTATION = "PROTECTED_MUTATION"


class ScanStatus(str, Enum):
    PASS = "PASS"
    FINDINGS = "FINDINGS"
    ERROR = "ERROR"
    NOT_RUN = "NOT_RUN"


def _require_sha(value: object, *, git: bool = False) -> str:
    if not isinstance(value, str) or ( _SHA1 if git else _SHA256).fullmatch(value) is None:
        raise CodeShieldHold()
    return value


def _require_token(value: object, pattern: re.Pattern[str] = _TOKEN) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise CodeShieldHold()
    return value


def checked_relative_path(value: object) -> str:
    """Lexical scope check. OS lstat/reparse/ADS and Git checks are separate."""
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise CodeShieldHold("UNSAFE_PATH")
    if (value.startswith("/") or "\\" in value or ":" in value or "\x00" in value
        or "//" in value or value.endswith("/") or "\n" in value or "\r" in value):
        raise CodeShieldHold("UNSAFE_PATH")
    parts = value.split("/")
    if len(parts) > 16:
        raise CodeShieldHold("UNSAFE_PATH")
    for part in parts:
        if (part in {"", ".", ".."} or part[-1:] in {".", " "}
            or any(ord(ch) < 32 for ch in part)
            or part.casefold() in _FORBIDDEN
            or part.casefold().startswith((".env", ".git", ".ssh", ".aws", ".npmrc", ".pypirc"))):
            raise CodeShieldHold("UNSAFE_PATH")
    return value


@dataclass(frozen=True)
class ScannerPin:
    """Protected-side expected binary/rule digest. Never trust guest-supplied pins."""
    tool: str
    version: str
    binary_sha256: str
    rules_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.tool not in _TOOLS:
            raise CodeShieldHold("UNPINNED_SCANNER")
        _require_token(self.version, _VERSION)
        _require_sha(self.binary_sha256)
        if self.rules_sha256 is not None:
            _require_sha(self.rules_sha256)
        if self.tool == "semgrep" and self.rules_sha256 is None:
            raise CodeShieldHold("UNPINNED_SCANNER")


@dataclass(frozen=True)
class CodeShieldContext:
    """Data contract, never a live owner approval or protected Git readback."""
    repository: str
    task_id: str
    run_id: str
    owner_consent_ref: str
    plan_sha256: str
    source_git_sha: str
    candidate_git_sha: str
    lease_epoch: int
    nonce_sha256: str
    allowed_paths: tuple[str, ...]
    data_class: DataClass
    scanner_pins: tuple[ScannerPin, ...]

    def __post_init__(self) -> None:
        if self.repository != "hibi89/my_local_ai":
            raise CodeShieldHold()
        for value in (self.task_id, self.run_id, self.owner_consent_ref):
            _require_token(value)
        _require_sha(self.plan_sha256)
        _require_sha(self.nonce_sha256)
        _require_sha(self.source_git_sha, git=True)
        _require_sha(self.candidate_git_sha, git=True)
        if type(self.lease_epoch) is not int or not 1 <= self.lease_epoch <= 2**63 - 1:
            raise CodeShieldHold()
        if not isinstance(self.data_class, DataClass):
            raise CodeShieldHold()
        if not isinstance(self.allowed_paths, tuple) or not 1 <= len(self.allowed_paths) <= 16:
            raise CodeShieldHold("UNSAFE_PATH")
        paths = [checked_relative_path(p) for p in self.allowed_paths]
        if len(set(p.casefold() for p in paths)) != len(paths) or tuple(sorted(paths)) != self.allowed_paths:
            raise CodeShieldHold("UNSAFE_PATH")
        if (not isinstance(self.scanner_pins, tuple) or len(self.scanner_pins) > len(_TOOLS)
            or any(not isinstance(pin, ScannerPin) for pin in self.scanner_pins)):
            raise CodeShieldHold("UNPINNED_SCANNER")
        tools = tuple(pin.tool for pin in self.scanner_pins)
        if len(set(tools)) != len(tools) or tools != tuple(sorted(tools)):
            raise CodeShieldHold("UNPINNED_SCANNER")

    @property
    def fingerprint_sha256(self) -> str:
        """Canonical digest binds a proposal; it is not a trusted signature."""
        doc = {
            "schema": "mla-codeshield-context/v1", "repository": self.repository,
            "task": self.task_id, "run": self.run_id,
            "owner_consent_ref": self.owner_consent_ref,
            "plan": self.plan_sha256, "source": self.source_git_sha,
            "candidate": self.candidate_git_sha, "lease": self.lease_epoch,
            "nonce": self.nonce_sha256, "paths": self.allowed_paths,
            "data_class": self.data_class.value,
            "scanners": [(p.tool, p.version, p.binary_sha256, p.rules_sha256)
                         for p in self.scanner_pins],
        }
        return sha256(json.dumps(doc, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class ScannerEvidence:
    """Bounded, redacted scan summary; not a signature or F18 receipt."""
    tool: str
    version: str
    binary_sha256: str
    rules_sha256: str | None
    context_sha256: str
    candidate_git_sha: str
    status: ScanStatus
    finding_count: int = 0

    def __post_init__(self) -> None:
        if self.tool not in _TOOLS:
            raise CodeShieldHold("UNPINNED_SCANNER")
        _require_token(self.version, _VERSION)
        _require_sha(self.binary_sha256)
        if self.rules_sha256 is not None:
            _require_sha(self.rules_sha256)
        _require_sha(self.context_sha256)
        _require_sha(self.candidate_git_sha, git=True)
        if not isinstance(self.status, ScanStatus):
            raise CodeShieldHold()
        if type(self.finding_count) is not int or not 0 <= self.finding_count <= 100000:
            raise CodeShieldHold()
        if ((self.status == ScanStatus.PASS and self.finding_count != 0)
            or (self.status == ScanStatus.FINDINGS and self.finding_count == 0)):
            raise CodeShieldHold()


@dataclass(frozen=True)
class CodeShieldAssessment:
    context_sha256: str
    outcome: RiskOutcome
    reasons: tuple[str, ...]
    execution_allowed: bool = False
    f18_independently_verified: bool = False
    owner_go_verified: bool = False
    git_promotion_allowed: bool = False
    remote_publish_allowed: bool = False

    def __post_init__(self) -> None:
        _require_sha(self.context_sha256)
        if not isinstance(self.outcome, RiskOutcome):
            raise CodeShieldHold("UNTRUSTED_DECISION")
        if (self.execution_allowed is not False
            or self.f18_independently_verified is not False
            or self.owner_go_verified is not False
            or self.git_promotion_allowed is not False
            or self.remote_publish_allowed is not False):
            raise CodeShieldHold("UNTRUSTED_DECISION")
        if (not isinstance(self.reasons, tuple) or not 1 <= len(self.reasons) <= 8
            or any(not isinstance(x, str) or not re.fullmatch(r"[A-Z_]{3,48}", x)
                   for x in self.reasons)):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def assess_static_only(
    context: CodeShieldContext, evidence: tuple[ScannerEvidence, ...],
    *, action: ActionKind = ActionKind.STATIC_READ,
) -> CodeShieldAssessment:
    """Fail-closed summary for preflight metadata; never an execution grant.

    The protected Controller must independently recompute context, pins, path
    inventory and scan outputs. A model-supplied assessment is never trusted.
    """
    if not isinstance(context, CodeShieldContext) or not isinstance(action, ActionKind):
        raise CodeShieldHold()
    if not isinstance(evidence, tuple) or len(evidence) > len(_TOOLS):
        raise CodeShieldHold()
    pinned = {pin.tool: pin for pin in context.scanner_pins}
    seen: set[str] = set()
    stale = False
    alerts = False
    for item in evidence:
        if not isinstance(item, ScannerEvidence) or item.tool in seen:
            raise CodeShieldHold("UNTRUSTED_DECISION")
        seen.add(item.tool)
        pin = pinned.get(item.tool)
        if (pin is None or item.version != pin.version
            or item.binary_sha256 != pin.binary_sha256
            or item.rules_sha256 != pin.rules_sha256
            or item.context_sha256 != context.fingerprint_sha256
            or item.candidate_git_sha != context.candidate_git_sha):
            stale = True
        if item.status == ScanStatus.FINDINGS:
            alerts = True
        elif item.status != ScanStatus.PASS:
            stale = True
    if action == ActionKind.PROTECTED_MUTATION or context.data_class in {
        DataClass.OWNER_PROTECTED, DataClass.CUSTOMER_SECRET,
    }:
        return CodeShieldAssessment(context.fingerprint_sha256,
                                    RiskOutcome.HOLD_HIGH_RISK, ("PROTECTED_SCOPE",))
    if alerts:
        return CodeShieldAssessment(context.fingerprint_sha256,
                                    RiskOutcome.HOLD_HIGH_RISK, ("SCANNER_FINDINGS",))
    if action == ActionKind.UNTRUSTED_EXECUTION:
        return CodeShieldAssessment(context.fingerprint_sha256,
                                    RiskOutcome.REQUIRES_ISOLATION_HOLD,
                                    ("UNTRUSTED_EXECUTION",))
    if stale or not pinned or seen != set(pinned):
        return CodeShieldAssessment(context.fingerprint_sha256,
                                    RiskOutcome.UNKNOWN_HOLD,
                                    ("MISSING_OR_STALE_SCANNER",))
    return CodeShieldAssessment(context.fingerprint_sha256,
                                RiskOutcome.ALLOW_NON_EXECUTING,
                                ("STATIC_CHECK_ONLY",))
