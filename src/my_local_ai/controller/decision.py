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
from my_local_ai.advisors.eai import parse_advisory

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

    def propose(
        self, states: dict[str, str], *,
        independently_verified: Iterable[str] = (),
        active_leases: Iterable[str] = (),
        advisory_json: str | None = None,
    ) -> ControllerResult:
        """Return only passive proposals, even for self-claimed APPROVED plans.

        Trusted review IDs are supplied by a protected owner-side caller;
        nothing in PlanSpec, advisor text or queue state can mint them.
        """
        candidates = self._queue.propose_ready(
            states, independently_verified=independently_verified,
            active_leases=active_leases,
        )
        candidate_ids = frozenset(c.task_id for c in candidates)
        hints: dict[str, int] = {}
        status = "DISABLED"
        if advisory_json is not None:
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
