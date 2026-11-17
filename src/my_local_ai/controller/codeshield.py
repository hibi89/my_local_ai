"""Real CodeShield static decision aggregation; no execution or approval path.

This controller-side entrypoint combines bounded AST and scanner evidence into a
fail-closed decision. The entire result is *advisory input* to a separately
protected owner F18/OS execution gate, never its authentication.
"""
from __future__ import annotations

from dataclasses import dataclass

from my_local_ai.security.ast_preflight import (
    ASTPreflight, scan_python_sources,
)
from my_local_ai.security.codeshield_contracts import (
    ActionKind, CodeShieldAssessment, CodeShieldContext, CodeShieldHold,
    RiskOutcome, ScannerEvidence, assess_static_only,
)

_PRIORITY = {
    RiskOutcome.ALLOW_NON_EXECUTING: 0,
    RiskOutcome.REQUIRES_ISOLATION_HOLD: 1,
    RiskOutcome.UNKNOWN_HOLD: 2,
    RiskOutcome.HOLD_HIGH_RISK: 3,
}


@dataclass(frozen=True)
class CodeShieldDecision:
    context_sha256: str
    candidate_git_sha: str
    outcome: RiskOutcome
    reason_codes: tuple[str, ...]
    ast: ASTPreflight
    scanner: CodeShieldAssessment
    stage: str = "P1_STATIC_CANDIDATE_ONLY"
    execution_allowed: bool = False
    owner_go_verified: bool = False
    f18_verified: bool = False
    git_update_allowed: bool = False
    remote_publish_allowed: bool = False

    def __post_init__(self) -> None:
        if (self.stage != "P1_STATIC_CANDIDATE_ONLY"
            or any(getattr(self, field) is not False for field in (
                "execution_allowed", "owner_go_verified", "f18_verified",
                "git_update_allowed", "remote_publish_allowed",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def evaluate_codeshield_candidate(
    context: CodeShieldContext, *,
    candidate_python_sources: dict[str, bytes | str],
    scanner_evidence: tuple[ScannerEvidence, ...] = (),
    action: ActionKind = ActionKind.STATIC_READ,
) -> CodeShieldDecision:
    """Bounded read-only source preflight with independent non-exec risk result.

    Caller must obtain a *protected* context, candidate snapshot and scanner
    output. Those properties cannot be authenticated by this Python object,
    so even a nominal ALLOW_NON_EXECUTING verdict is not a runtime grant.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    ast_result = scan_python_sources(context, candidate_python_sources)
    scanners = assess_static_only(context, scanner_evidence, action=action)
    outcome = max((ast_result.outcome, scanners.outcome), key=_PRIORITY.__getitem__)
    reasons = tuple(sorted(set((ast_result.reason, *scanners.reasons))))
    return CodeShieldDecision(
        context.fingerprint_sha256, context.candidate_git_sha,
        outcome, reasons, ast_result, scanners,
    )


def read_only_decision_status(decision: CodeShieldDecision) -> dict[str, object]:
    """Minimal UI/CLI transport: no source body, secret, command, path or keys."""
    if not isinstance(decision, CodeShieldDecision):
        raise CodeShieldHold()
    return {
        "stage": decision.stage,
        "context_sha256": decision.context_sha256,
        "candidate_git_sha": decision.candidate_git_sha,
        "outcome": decision.outcome.value,
        "reasons": list(decision.reason_codes),
        "finding_count_capped": min(len(decision.ast.findings), 32),
        "execution_allowed": False,
        "owner_go_verified": False,
        "f18_verified": False,
        "can_write_git": False,
        "can_publish_remote": False,
    }

# Sequential local-only code inspection. P1 source flow only; no untrusted
# Python imports, test execution, F18 signing, owner consent, or Git writes.
from pathlib import Path as _Path
from my_local_ai.security.ast_preflight import scan_scoped_python_sources
from my_local_ai.security.ruff_adapter import run_ruff_static
from my_local_ai.security.semgrep_adapter import run_local_semgrep, inspect_packaged_semgrep_rules
from my_local_ai.security.supply_chain import (
    scan_gitleaks_stdin, inspect_osv_offline_cache, OfflineDatabasePin,
)
from my_local_ai.security.codeshield_contracts import ScanStatus
import re as _re
from my_local_ai.security.codeshield_contracts import checked_relative_path as _checked_relative_path


@dataclass(frozen=True)
class LocalStaticAudit:
    context_sha256: str
    candidate_sha: str
    outcome: RiskOutcome
    status_by_scanner: tuple[tuple[str, str], ...]
    reason_codes: tuple[str, ...]
    changed_file_digests: tuple[tuple[str, str], ...]
    stage: str = "UNTRUSTED_STATIC_REPORT_F18_AND_OWNER_HOLD"
    execution_allowed: bool = False
    owner_go_verified: bool = False
    independent_f18_verified: bool = False
    git_promotion_allowed: bool = False

    def __post_init__(self) -> None:
        if (self.stage != "UNTRUSTED_STATIC_REPORT_F18_AND_OWNER_HOLD"
            or any(getattr(self, name) is not False for name in (
                "execution_allowed", "owner_go_verified",
                "independent_f18_verified", "git_promotion_allowed",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")

        if (not isinstance(self.context_sha256, str)
            or _re.fullmatch(r"[0-9a-f]{64}", self.context_sha256) is None
            or not isinstance(self.candidate_sha, str)
            or _re.fullmatch(r"[0-9a-f]{40}", self.candidate_sha) is None
            or not isinstance(self.outcome, RiskOutcome)
            or not isinstance(self.status_by_scanner, tuple)
            or not 1 <= len(self.status_by_scanner) <= 8
            or not isinstance(self.reason_codes, tuple)
            or not 1 <= len(self.reason_codes) <= 32
            or any(not isinstance(code, str)
                   or _re.fullmatch(r"[A-Z0-9_]{3,96}", code) is None
                   for code in self.reason_codes)
            or not isinstance(self.changed_file_digests, tuple)
            or len(self.changed_file_digests) > 16):
            raise CodeShieldHold("UNTRUSTED_DECISION")
        possible = {
            "ast": {item.value for item in RiskOutcome},
            "ruff": {item.value for item in ScanStatus},
            "gitleaks": {item.value for item in ScanStatus},
            "semgrep": {item.value for item in ScanStatus},
            "semgrep_rules": {"PIN_MATCH", "UNKNOWN_HOLD"},
            "osv_cache": {"PIN_MATCH", "UNKNOWN_HOLD"},
        }
        encountered: set[str] = set()
        for item in self.status_by_scanner:
            if (not isinstance(item, tuple) or len(item) != 2
                or not isinstance(item[0], str) or item[0] in encountered
                or item[0] not in possible or item[1] not in possible[item[0]]):
                raise CodeShieldHold("UNTRUSTED_DECISION")
            encountered.add(item[0])
        path_aliases: set[str] = set()
        for item in self.changed_file_digests:
            if (not isinstance(item, tuple) or len(item) != 2
                or not isinstance(item[0], str)
                or not isinstance(item[1], str)
                or _re.fullmatch(r"[0-9a-f]{64}", item[1]) is None):
                raise CodeShieldHold("UNTRUSTED_DECISION")
            _checked_relative_path(item[0])
            if item[0].casefold() in path_aliases:
                raise CodeShieldHold("UNTRUSTED_DECISION")
            path_aliases.add(item[0].casefold())

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "context_sha256": self.context_sha256,
            "candidate_git_sha": self.candidate_sha,
            "outcome": self.outcome.value,
            "status_by_scanner": dict(self.status_by_scanner),
            "reasons": list(self.reason_codes),
            "changed_file_sha256": dict(self.changed_file_digests),
            "stage": self.stage,
            "execution_allowed": False,
            "independent_f18_verified": False,
            "owner_go_verified": False,
            "git_promotion_allowed": False,
        }


def audit_scoped_sources(
    context: CodeShieldContext, *, worktree: str | _Path,
    original_checkout: str | _Path, changed_python_paths: tuple[str, ...],
    ruff_binary: str | _Path | None = None,
    gitleaks_binary: str | _Path | None = None,
    semgrep_binary: str | _Path | None = None,
    local_semgrep_rules: str | _Path | None = None,
    local_osv_cache: str | _Path | None = None,
    offline_database_pin: OfflineDatabasePin | None = None,
) -> LocalStaticAudit:
    """Read actual scoped files, then invoke explicitly supplied pinned tools.

    In this phase Semgrep stays in HOLD: proof of network-denied OS principal
    is not implemented. Calls only local Ruff/Gitleaks binaries if supplied.
    The entire audit remains an untrusted P1 *static* result that cannot grant
    F18, owner authority or any form of code/script execution.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    ast_report = scan_scoped_python_sources(
        context, worktree=worktree, original_checkout=original_checkout,
        changed_paths=changed_python_paths,
    )
    statuses: list[tuple[str, str]] = [("ast", ast_report.outcome.value)]
    reasons = [ast_report.reason]
    evidences: list[ScannerEvidence] = []
    # Do not spawn any scanner if AST identified high risk/unstable sources.
    if ast_report.outcome in (RiskOutcome.HOLD_HIGH_RISK, RiskOutcome.UNKNOWN_HOLD):
        statuses.extend([
            ("ruff", ScanStatus.NOT_RUN.value),
            ("gitleaks", ScanStatus.NOT_RUN.value),
            ("semgrep", ScanStatus.NOT_RUN.value),
        ])
        reasons.append("STATIC_SOURCE_HOLD")
        final = RiskOutcome.HOLD_HIGH_RISK if ast_report.outcome == RiskOutcome.HOLD_HIGH_RISK else RiskOutcome.UNKNOWN_HOLD
        return LocalStaticAudit(
            context.fingerprint_sha256, context.candidate_git_sha, final,
            tuple(statuses), tuple(sorted(set(reasons))), ast_report.file_digests,
        )

    if ruff_binary is not None:
        ruff = run_ruff_static(
            context, binary=ruff_binary, worktree=worktree,
            original_checkout=original_checkout,
            python_paths=changed_python_paths,
        )
        statuses.append(("ruff", ruff.status.value))
        if ruff.evidence is not None:
            evidences.append(ruff.evidence)
        if ruff.status != ScanStatus.PASS:
            reasons.append(ruff.reason)
    else:
        statuses.append(("ruff", ScanStatus.NOT_RUN.value))
    if gitleaks_binary is not None:
        leaks = scan_gitleaks_stdin(
            context, binary=gitleaks_binary, worktree=worktree,
            original_checkout=original_checkout,
            changed_paths=changed_python_paths,
        )
        statuses.append(("gitleaks", leaks.scan_status.value))
        if leaks.evidence is not None:
            evidences.append(leaks.evidence)
        if leaks.scan_status != ScanStatus.PASS:
            reasons.append(leaks.reason)
    else:
        statuses.append(("gitleaks", ScanStatus.NOT_RUN.value))
    local_rules = inspect_packaged_semgrep_rules(context)
    statuses.append(("semgrep_rules",
                     "PIN_MATCH" if local_rules.state ==
                     "LOCAL_RULES_PINNED_STATIC_ONLY" else "UNKNOWN_HOLD"))
    if local_rules.state != "LOCAL_RULES_PINNED_STATIC_ONLY":
        reasons.append("LOCAL_RULES_HOLD")
    # This intentionally never passes a self-asserted OS egress attestation.
    # The eventual protected runner must provide proof in its own trust root.
    if semgrep_binary is not None and local_semgrep_rules is not None:
        semgrep = run_local_semgrep(
            context, executable=semgrep_binary, local_rules=local_semgrep_rules,
            disposable_worktree=worktree, original_checkout=original_checkout,
            changed_paths=changed_python_paths, owner_protected_no_egress=False,
        )
        statuses.append(("semgrep", semgrep.status.value))
        if semgrep.evidence is not None:
            evidences.append(semgrep.evidence)
        if semgrep.status != ScanStatus.PASS:
            reasons.append(semgrep.reason)
    else:
        statuses.append(("semgrep", ScanStatus.NOT_RUN.value))
    # Lockfile-dependent OSV checks are conditional. A local cache hash/age
    # is data-only and never represents a completed vulnerability scan.
    if (local_osv_cache is None) != (offline_database_pin is None):
        raise CodeShieldHold("UNPINNED_SCANNER")
    if local_osv_cache is not None:
        cache = inspect_osv_offline_cache(
            offline_database_pin, cache_root=local_osv_cache,
            worktree=worktree, original_checkout=original_checkout,
        )
        statuses.append(("osv_cache", "PIN_MATCH" if cache.state ==
                         "CACHE_PIN_MATCH_STATIC_ONLY" else "UNKNOWN_HOLD"))
        if cache.state != "CACHE_PIN_MATCH_STATIC_ONLY":
            reasons.append("OFFLINE_DB_HOLD")
    scanner = assess_static_only(
        context, tuple(evidences), action=ActionKind.STATIC_READ,
    )
    outcome = max(
        (ast_report.outcome, scanner.outcome),
        key=_PRIORITY.__getitem__,
    )
    reasons.extend(scanner.reasons)
    if any(status != ScanStatus.PASS.value for tool, status in statuses if tool != "ast"):
        outcome = max((outcome, RiskOutcome.UNKNOWN_HOLD), key=_PRIORITY.__getitem__)
        reasons.append("MISSING_OR_HELD_LOCAL_SCANNER")
    return LocalStaticAudit(
        context.fingerprint_sha256, context.candidate_git_sha,
        outcome, tuple(statuses), tuple(sorted(set(reasons))),
        ast_report.file_digests,
    )


# CS-SWU-014: Controller's hard-stop order, still P1 SOURCE ONLY.
# This is never a trusted OS execution/signer/CAS implementation.
_DISPATCH_STAGES = (
    "SOURCE_PLAN_LEASE", "WORKTREE_SCOPE", "STATIC_SCANNERS",
    "OWNER_ACTION_GRANT", "WINDOWS_NO_EGRESS_BROKER",
    "INDEPENDENT_F18", "GIT_CAS_PROMOTION",
)


@dataclass(frozen=True)
class ProtectedDispatchHold:
    context_sha256: str
    candidate_git_sha: str
    action: ActionKind
    outcome: RiskOutcome
    stage_results: tuple[tuple[str, str], ...]
    reason_codes: tuple[str, ...]
    stage: str = "P1_CONTROLLER_DISPATCH_DENIED"
    scanner_pass_authorizes_execution: bool = False
    owner_consent_verified: bool = False
    isolated_runtime_attested: bool = False
    f18_independently_verified: bool = False
    git_cas_verified: bool = False
    may_launch_untrusted: bool = False
    may_mutate_original: bool = False
    may_promote_git: bool = False

    def __post_init__(self) -> None:
        if (self.stage != "P1_CONTROLLER_DISPATCH_DENIED"
            or not isinstance(self.action, ActionKind)
            or not isinstance(self.outcome, RiskOutcome)
            or len(self.stage_results) != len(_DISPATCH_STAGES)
            or tuple(name for name, _ in self.stage_results) != _DISPATCH_STAGES
            or any(state not in {"HOLD", "SOURCE_SHAPE_ONLY", "FAILED"}
                   for _, state in self.stage_results)
            or not isinstance(self.reason_codes, tuple)
            or not self.reason_codes
            or any(getattr(self, field) is not False for field in (
                "scanner_pass_authorizes_execution", "owner_consent_verified",
                "isolated_runtime_attested", "f18_independently_verified",
                "git_cas_verified", "may_launch_untrusted",
                "may_mutate_original", "may_promote_git",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "context_sha256": self.context_sha256,
            "candidate_git_sha": self.candidate_git_sha,
            "action": self.action.value,
            "outcome": self.outcome.value,
            "checks": dict(self.stage_results),
            "reason_codes": list(self.reason_codes),
            "owner_consent_verified": False,
            "isolated_runtime_attested": False,
            "f18_independently_verified": False,
            "git_cas_verified": False,
            "execution_allowed": False,
            "can_modify_original": False,
            "can_promote_git": False,
            "can_publish_remote": False,
        }


def preview_protected_dispatch_hold(
    context: CodeShieldContext, *,
    audit: LocalStaticAudit | None = None,
    action: ActionKind = ActionKind.UNTRUSTED_EXECUTION,
) -> ProtectedDispatchHold:
    """Deterministic Controller stop before any runtime/owner/Git capability.

    Matching an in-memory audit is a consistency check only, never a fresh
    Git diff, signed owner consent, trusted F18 receipt or Windows OS proof.
    Even an ALLOW_NON_EXECUTING static result cannot change this HOLD.
    """
    if (not isinstance(context, CodeShieldContext)
        or not isinstance(action, ActionKind)):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    reasons = []
    stages = {
        "SOURCE_PLAN_LEASE": "SOURCE_SHAPE_ONLY",
        "WORKTREE_SCOPE": "HOLD",
        "STATIC_SCANNERS": "HOLD",
        "OWNER_ACTION_GRANT": "HOLD",
        "WINDOWS_NO_EGRESS_BROKER": "HOLD",
        "INDEPENDENT_F18": "HOLD",
        "GIT_CAS_PROMOTION": "HOLD",
    }
    if audit is None:
        reasons.append("STATIC_AUDIT_MISSING")
        outcome = RiskOutcome.UNKNOWN_HOLD
    elif not isinstance(audit, LocalStaticAudit):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    elif (audit.context_sha256 != context.fingerprint_sha256
          or audit.candidate_sha != context.candidate_git_sha):
        reasons.append("CONTEXT_SOURCE_MISMATCH")
        stages["STATIC_SCANNERS"] = "FAILED"
        outcome = RiskOutcome.UNKNOWN_HOLD
    elif (audit.execution_allowed or audit.owner_go_verified
          or audit.independent_f18_verified or audit.git_promotion_allowed
          or audit.stage != "UNTRUSTED_STATIC_REPORT_F18_AND_OWNER_HOLD"):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    else:
        # Status tuples can be guest-authored. A 'PASS' here is source-shape
        # only and MUST NOT set owner, F18, OS or Git permissions.
        if (len(audit.status_by_scanner) > 8
            or len({name for name, _ in audit.status_by_scanner})
               != len(audit.status_by_scanner)
            or not audit.status_by_scanner):
            raise CodeShieldHold("UNTRUSTED_DECISION")
        stages["WORKTREE_SCOPE"] = "SOURCE_SHAPE_ONLY"
        if (audit.outcome == RiskOutcome.HOLD_HIGH_RISK):
            reasons.append("SCANNER_HIGH_RISK_HOLD")
            stages["STATIC_SCANNERS"] = "FAILED"
            outcome = RiskOutcome.HOLD_HIGH_RISK
        elif audit.outcome == RiskOutcome.UNKNOWN_HOLD:
            reasons.append("SCANNER_UNKNOWN_HOLD")
            outcome = RiskOutcome.UNKNOWN_HOLD
        elif audit.outcome == RiskOutcome.REQUIRES_ISOLATION_HOLD:
            reasons.append("ISOLATION_REQUIRED")
            outcome = RiskOutcome.REQUIRES_ISOLATION_HOLD
        else:
            reasons.append("STATIC_PASS_NOT_EXECUTION_GRANT")
            stages["STATIC_SCANNERS"] = "SOURCE_SHAPE_ONLY"
            outcome = RiskOutcome.REQUIRES_ISOLATION_HOLD
    if action == ActionKind.PROTECTED_MUTATION:
        outcome = RiskOutcome.HOLD_HIGH_RISK
        reasons.append("PROTECTED_ACTION_NO_GRANT")
    elif action == ActionKind.UNTRUSTED_EXECUTION:
        reasons.append("UNTRUSTED_EXECUTION_DENIED")
    else:
        reasons.append("STATIC_ONLY_NO_DISPATCH")
    reasons.extend(("OWNER_ACTION_NOT_ATTESTED", "F18_OS_CAS_NOT_ATTESTED"))
    return ProtectedDispatchHold(
        context.fingerprint_sha256, context.candidate_git_sha,
        action, outcome,
        tuple((stage, stages[stage]) for stage in _DISPATCH_STAGES),
        tuple(sorted(set(reasons))),
    )


# CS-SWU-014 supporting port: expose the inert CS-SWU-007 offline fallback.
# It is only a read-only planning path, not a Windows Sandbox launcher.
from my_local_ai.security.semgrep_adapter import (
    prepare_protected_semgrep_request as _prepare_semgrep_request,
    prepare_on_demand_sandbox_fallback as _prepare_semgrep_sandbox_fallback,
)


def preview_semgrep_sandbox_fallback(
    context: CodeShieldContext, *,
    executable: str | _Path, local_rules: str | _Path,
    disposable_worktree: str | _Path,
    original_checkout: str | _Path,
    changed_paths: tuple[str, ...],
    minimal_staging_folder: str | _Path,
) -> dict[str, object]:
    """Controller => pinned static request => sealed no-network WSB preview.

    It never writes a .wsb file, starts Sandbox, changes Windows features,
    grants execution or signs a CodeShield decision. Outputs are redacted.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    req = _prepare_semgrep_request(
        context, executable=executable, local_rules=local_rules,
        disposable_worktree=disposable_worktree,
        original_checkout=original_checkout,
        changed_paths=changed_paths,
    )
    preview = _prepare_semgrep_sandbox_fallback(
        req, minimal_staging_folder=minimal_staging_folder,
    )
    result = preview.to_redacted_dict()
    if (result.get("may_launch_sandbox") is not False
        or result.get("may_run_scanner") is not False
        or result.get("os_isolation_attested") is not False
        or result.get("f18_verified") is not False
        or result.get("git_promotion_allowed") is not False):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    return result
