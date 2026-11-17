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
