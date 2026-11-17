"""Non-executing controller supervisor. No self-restart, process kill or timers."""
from __future__ import annotations

from dataclasses import dataclass
from my_local_ai.ops.resource_monitor import (
    ResourceAssessment, ResourceLimits,ResourceReading, assess_resources,
)


@dataclass(frozen=True)
class SupervisorProposal:
    state: str
    reasons: tuple[str, ...]
    req_code_ready: bool
    operator_go_verified: bool = False
    auto_restart_allowed: bool = False
    process_signal_allowed: bool = False
    network_allowed: bool = False
    long_run_verified: bool = False


def assess_supervisor(
    *, resource_reading: ResourceReading,
    resource_limits: ResourceLimits,
    code_ready: bool,
    lease_epoch: int,
    attempts: int,
    owner_go_claimed: bool = False,
) -> SupervisorProposal:
    """Never mistake a boolean owner claim for a protected signer."""
    if (type(code_ready) is not bool or type(lease_epoch) is not int
        or lease_epoch < 0 or type(attempts) is not int or not 0 <= attempts <= 2):
        raise ValueError("invalid supervised run metadata")
    observed=assess_resources(resource_reading,resource_limits)
    if observed.state=="HOLD":
        return SupervisorProposal("RESOURCE_HOLD",observed.reasons,code_ready)
    if not code_ready:
        return SupervisorProposal("CODE_NOT_READY",("CODE_DEPENDENCIES",),False)
    if attempts>=2:
        return SupervisorProposal("REPAIR_EXHAUSTED",("MAX_TWO_ATTEMPTS",),True)
    if lease_epoch==0:
        return SupervisorProposal("NO_TRUSTED_LEASE",("MISSING_LEASE",),True)
    if owner_go_claimed:
        return SupervisorProposal("OWNER_CLAIM_UNVERIFIED",("PROTECTED_SIGNER_REQUIRED",),True)
    return SupervisorProposal("READY_CODE_ONLY",("F18_OS_GATE_AND_OWNER_GO_REQUIRED",),True)
