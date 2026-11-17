"""My Local AI's own deterministic decision engine (non-executing P1 candidate).

This module is original clean-room source, not an import from EAI/AX Dev Factory.
All proposals are *non-authoritative*: a protected owner signer, OS-isolated
coder, F18 reviewer and integration gate must decide whether to run anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from my_local_ai.ax_runtime.queue import QueuePolicy
from my_local_ai.contracts.plan import PlanSpec
from my_local_ai.contracts.task import TaskSpec
from my_local_ai.advisors.eai import parse_advisory, inspect_optional_eai

_RISK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class Decision:
    task_id: str
    plan_sha256: str
    source_sha: str
    required_verified: tuple[str, ...]
    risk: str
    reason: str
    runnable: bool = False


@dataclass(frozen=True)
class ControllerResult:
    decisions: tuple[Decision, ...]
    advisory_status: str
    owner_go: bool = False
    verified: bool = False
    execution_allowed: bool = False




@dataclass(frozen=True)
class CodeBatchPreview:
    plan_sha256: str
    source_sha: str
    task_ids: tuple[str, ...]
    deferred: tuple[tuple[str, str], ...]
    reserved_calls: int
    reserved_seconds: int
    advisory_status: str
    state: str = "CODE_CANDIDATE_ONLY"
    model_calls_executed: int = 0
    owner_go_verified: bool = False
    independent_f18_verified: bool = False
    runnable: bool = False

class Controller:
    """Deterministic READY ranking; no EAI process, shell or network access."""

    def __init__(self, plan: PlanSpec):
        if not isinstance(plan, PlanSpec) or not plan.tasks:
            raise ValueError("validated plan required")
        if len({task.task_id for task in plan.tasks}) != len(plan.tasks):
            raise ValueError("duplicate plan tasks")
        if any(task.source_sha != plan.blueprint_sha for task in plan.tasks):
            raise ValueError("source revision drift")
        self._plan = plan
        self._tasks = {task.task_id: task for task in plan.tasks}
        self._queue = QueuePolicy(plan.tasks, plan.digest)

    def propose_code_batch(
        self, states: dict[str, str], *,
        max_tasks: int, max_total_calls: int, max_total_seconds: int,
        independently_verified: Iterable[str] = (),
        active_leases: Iterable[str] = (),
        advisory_json: str | None = None,
        optional_eai_envelope_json: str | None = None,
    ) -> "CodeBatchPreview":
        """Select disjoint *candidate code tasks*, never parallel executors.

        The physical one-model lock, owner GO, source rights, F18 and OS
        sandbox remain separate. This resolves queue bottlenecks without
        treating advisory priority or guest VERIFIED claims as privileges.
        """
        if (type(max_tasks) is not int or not 1 <= max_tasks <= 32
            or type(max_total_calls) is not int or not 1 <= max_total_calls <= 100
            or type(max_total_seconds) is not int
            or not 1 <= max_total_seconds <= 86400):
            raise ValueError("invalid code authoring batch budget")
        result = self.propose(
            states,independently_verified=independently_verified,
            active_leases=active_leases,advisory_json=advisory_json,
            optional_eai_envelope_json=optional_eai_envelope_json,
        )
        if result.execution_allowed or result.verified or result.owner_go:
            raise ValueError("untrusted Controller privilege")
        selected=[]
        deferred=[]
        used_files=set()
        calls=0
        seconds=0
        for entry in result.decisions:
            if entry.runnable:
                raise ValueError("unexpected executable candidate")
            task=self._tasks[entry.task_id]
            paths={v.casefold() for v in task.allowed_paths}
            if len(selected)>=max_tasks:
                deferred.append((entry.task_id,"SLOT_BUDGET"))
                continue
            if paths & used_files:
                deferred.append((entry.task_id,"PATH_CONFLICT"))
                continue
            if (calls+task.resource_budget.max_calls>max_total_calls
                or seconds+task.resource_budget.max_seconds>max_total_seconds):
                deferred.append((entry.task_id,"RESOURCE_BUDGET"))
                continue
            used_files.update(paths)
            calls+=task.resource_budget.max_calls
            seconds+=task.resource_budget.max_seconds
            selected.append(entry.task_id)
        return CodeBatchPreview(
            self._plan.digest,self._plan.blueprint_sha,tuple(selected),
            tuple(deferred),calls,seconds,result.advisory_status,
        )

    def propose(
        self, states: dict[str, str], *,
        independently_verified: Iterable[str] = (),
        active_leases: Iterable[str] = (),
        advisory_json: str | None = None,
        optional_eai_envelope_json: str | None = None,
    ) -> ControllerResult:
        """Return only passive proposals, even for self-claimed APPROVED plans.

        Trusted review IDs are supplied by a protected owner-side caller;
        nothing in PlanSpec, advisor text or queue state can mint them.
        """
        if advisory_json is not None and optional_eai_envelope_json is not None:
            raise ValueError("two competing advisor sources are not allowed")
        candidates = self._queue.propose_ready(
            states, independently_verified=independently_verified,
            active_leases=active_leases,
        )
        candidate_ids = frozenset(c.task_id for c in candidates)
        hints: dict[str, int] = {}
        status = "DISABLED"
        if optional_eai_envelope_json is not None:
            # Pin the optional advisor's text to the exact immutable plan
            # and source, *after* the native DAG/lease READY calculation.
            # Importing/running the original EAI product is never necessary.
            advisory = inspect_optional_eai(
                envelope_json=optional_eai_envelope_json,
                eligible_ids=candidate_ids,
                trusted_source_sha=self._plan.blueprint_sha,
                trusted_plan_sha=self._plan.digest,
            )
            if advisory.executable or not advisory.independent_controller_required:
                raise ValueError("unsafe optional advisor authority")
            if advisory.status == "OPTIONAL_HINTS_VALIDATED_ONLY":
                hints = dict(advisory.hints)
                status = "OPTIONAL_HINTS_ACCEPTED"
            else:
                status = "INVALID_HINTS_IGNORED"
        elif advisory_json is not None:
            try:
                hints = parse_advisory(advisory_json, candidate_ids)
                status = "OPTIONAL_HINTS_ACCEPTED"
            except (TypeError, ValueError):
                status = "INVALID_HINTS_IGNORED"
        # Risk is the immutable first sort key. Advisory can reorder only
        # otherwise equal-risk READY tasks, never expand the task set.
        ordered = sorted(
            candidates,
            key=lambda item: (
                _RISK[self._tasks[item.task_id].risk],
                hints.get(item.task_id, 5),
                item.task_id,
            ),
        )
        decisions = tuple(
            Decision(
                task_id=c.task_id, plan_sha256=c.plan_sha,
                source_sha=self._tasks[c.task_id].source_sha,
                required_verified=c.required_verified,
                risk=self._tasks[c.task_id].risk,
                reason="READY_PROPOSAL_ONLY",
            )
            for c in ordered
        )
        return ControllerResult(decisions, status)
