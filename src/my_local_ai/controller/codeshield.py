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
from my_local_ai.security.supply_chain import scan_gitleaks_stdin
from my_local_ai.security.codeshield_contracts import ScanStatus


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
