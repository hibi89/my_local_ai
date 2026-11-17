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
    if (type(code_ready) is not bool or type(owner_go_claimed) is not bool
        or type(lease_epoch) is not int
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


# SWU-033: connect resource decisions to a durable, fenced stop/pause
# checkpoint. This function never kills/restarts a process or resumes a lease.
@dataclass(frozen=True)
class SupervisorCheckpointResult:
    task_id: str
    state: str
    reasons: tuple[str, ...]
    checkpoint_written: bool
    lease_retained_for_fencing: bool
    may_execute: bool = False
    process_signal_allowed: bool = False
    auto_restart_allowed: bool = False
    verified_24h_run: bool = False


def supervise_owned_checkpoint(
    db_path, *, plan_id: str, task_id: str, run_id: str,
    plan_sha256: str, baseline_sha: str, protected_ref_sha: str | None,
    resource_reading: ResourceReading, resource_limits: ResourceLimits,
    code_ready: bool, lease_epoch: int, attempts: int,
    owner_go_claimed: bool = False,
) -> SupervisorCheckpointResult:
    """Record durable HOLD on limits/unsafe state; never auto-resume.

    Called by an owner-side controller after a read-only resource sample.
    Retained lease generation fences stale workers after interruption.
    Unknown CPU/thermal/VRAM measurements are HOLD, not fake PASS.
    """
    from my_local_ai.state.reconcile import reconcile_owned_crash_checkpoint
    import re

    if (not isinstance(task_id, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", task_id) is None
        or not isinstance(run_id, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", run_id) is None
        or type(lease_epoch) is not int or lease_epoch <= 0):
        raise ValueError("invalid supervisor checkpoint identity")
    policy = assess_supervisor(
        resource_reading=resource_reading,
        resource_limits=resource_limits,
        code_ready=code_ready, lease_epoch=lease_epoch,
        attempts=attempts, owner_go_claimed=owner_go_claimed,
    )
    if policy.state not in {
        "RESOURCE_HOLD", "REPAIR_EXHAUSTED", "CODE_NOT_READY",
        "OWNER_CLAIM_UNVERIFIED",
    }:
        # READY_CODE_ONLY does not mean owner/runtime permitted.
        return SupervisorCheckpointResult(
            task_id, "SOURCE_ONLY_NO_RUNTIME_GO", policy.reasons,
            False, False,
        )
    checkpoint = reconcile_owned_crash_checkpoint(
        db_path, plan_id=plan_id, task_id=task_id,
        trusted_plan_sha=plan_sha256,
        trusted_source_sha=baseline_sha,
        protected_ref_sha=protected_ref_sha,
        interrupted_run_id=run_id, interrupted_generation=lease_epoch,
    )
    if checkpoint.decision != "HOLD_INTERRUPTED_LEASE_REQUIRES_PROTECTED_RECONCILIATION":
        raise ValueError("unsafe supervisor recovery result")
    return SupervisorCheckpointResult(
        task_id, "DURABLE_RESOURCE_OR_POLICY_HOLD",
        policy.reasons, checkpoint.checkpoint_written, True,
    )
