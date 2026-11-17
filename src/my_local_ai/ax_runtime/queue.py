"""Pure deterministic DAG/READY selection. No execution or trusted-review authority.

The caller must supply trusted dependency states from the protected controller;
a model's claimed VERIFIED status never suffices.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable

from my_local_ai.contracts.task import TaskSpec

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_STATES = frozenset({
    "QUEUED", "READY", "LEASED", "CODING", "REVIEW_PENDING",
    "REPAIR_ONCE", "HOLD", "BLOCKED_DEPENDENCY", "AWAITING_OWNER",
    "INTERRUPTED", "VERIFIED",
})

@dataclass(frozen=True)
class ReadyCandidate:
    task_id: str
    required_verified: tuple[str, ...]
    plan_sha: str
    runnable: bool = False  # only the separately authorized executor may start

class QueuePolicy:
    """Validate an immutable DAG and produce non-executing READY candidates."""

    def __init__(self, tasks: Iterable[TaskSpec], plan_sha: str):
        values = tuple(tasks)
        if (not isinstance(plan_sha, str) or not _SHA256.fullmatch(plan_sha)
            or not 1 <= len(values) <= 512):
            raise ValueError("bounded tasks and SHA256 plan digest required")
        if any(not isinstance(task, TaskSpec) or task.plan_sha != plan_sha for task in values):
            raise ValueError("task plan SHA mismatch or invalid task")
        self._tasks = {t.task_id: t for t in values}
        if len(self._tasks) != len(values):
            raise ValueError("duplicate tasks")
        if any(not set(t.depends_on).issubset(self._tasks) for t in values):
            raise ValueError("unknown task dependency")
        seen: set[str] = set()
        visiting: set[str] = set()
        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("cyclic dependency")
            if task_id in seen:
                return
            visiting.add(task_id)
            for dep in self._tasks[task_id].depends_on:
                visit(dep)
            visiting.remove(task_id)
            seen.add(task_id)
        for task_id in self._tasks:
            visit(task_id)
        self.plan_sha = plan_sha

    def propose_ready(
        self,
        states: dict[str, str],
        *,
        independently_verified: Iterable[str] = (),
        active_leases: Iterable[str] = (),
    ) -> tuple[ReadyCandidate, ...]:
        """No READY proposals rely solely on a caller-provided state label.

        Independently verified IDs are still suggestions; this layer never executes.
        The F18 reviewer must populate the protected set in the integrated controller.
        """
        if not isinstance(states, dict) or set(states) != set(self._tasks):
            raise ValueError("missing or unknown task states")
        if any(state not in _STATES for state in states.values()):
            raise ValueError("invalid queue state")
        if isinstance(independently_verified, (str, bytes)):
            raise ValueError("trusted ID collection required")
        trusted = set(independently_verified)
        if not trusted.issubset(self._tasks):
            raise ValueError("unknown trusted dependency")
        if any(states[tid] != "VERIFIED" for tid in trusted):
            raise ValueError("inconsistent trusted dependency")
        if isinstance(active_leases, (str, bytes)):
            raise ValueError("active lease ID collection required")
        active = set(active_leases)
        if not active.issubset(self._tasks):
            raise ValueError("unknown active lease")
        result = []
        for task_id in sorted(self._tasks):
            task = self._tasks[task_id]
            if states[task_id] != "READY" or task_id in active:
                continue
            if all(dep in trusted for dep in task.depends_on):
                result.append(ReadyCandidate(task_id, task.depends_on, self.plan_sha))
        return tuple(result)

    @staticmethod
    def idempotency_key(plan_sha: str, task_id: str, baseline_sha: str) -> str:
        if not isinstance(plan_sha, str) or not _SHA256.fullmatch(plan_sha):
            raise ValueError("plan sha256")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", task_id):
            raise ValueError("task id")
        if not isinstance(baseline_sha, str) or not _GIT_SHA.fullmatch(baseline_sha):
            raise ValueError("Git baseline SHA")
        return hashlib.sha256(f"my-local-ai/v1|{plan_sha}|{task_id}|{baseline_sha}".encode("ascii")).hexdigest()
