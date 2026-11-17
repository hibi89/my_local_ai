"""Minimal redacted read-only dashboard snapshot. No secrets or raw task content."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

_MAX_BYTES = 1_048_576
_STATE_KEY = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")

@dataclass(frozen=True)
class StatusSnapshot:
    phase: str
    completed_req: int
    total_req: int
    task_total: int
    ready_tasks: int
    hold_tasks: int
    implemented_tasks: int
    p2_locked: bool = True
    verification: str = "UNASSESSED"
    owner_real_use_go: bool = False
    operation_allowed: bool = False

    def to_public_dict(self) -> dict:
        return {
            "phase": self.phase,
            "completed_req": self.completed_req,
            "total_req": self.total_req,
            "implementation_percent": round(self.completed_req * 100 / self.total_req, 2),
            "task_total": self.task_total,
            "ready_tasks": self.ready_tasks,
            "hold_tasks": self.hold_tasks,
            "implemented_tasks": self.implemented_tasks,
            "p2_locked": self.p2_locked,
            "verification": self.verification,
            "owner_real_use_go": self.owner_real_use_go,
            "operation_allowed": self.operation_allowed,
            "provider_remote": "OFF_NOT_APPROVED",
            "browser_validation": "DEFERRED_TO_P2",
        }

def _read_limited(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError("symlink status file")
    with path.open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError("oversized status")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("malformed status")
    return data

def load_snapshot(project_root: str | Path) -> StatusSnapshot:
    root = Path(project_root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("unsafe status root")
    gate = _read_limited(root / "WORK_PHASE_GATES.json")
    queue = _read_limited(root / "INSTANT_TASK_QUEUE.json")
    if gate.get("program") != "my_local_ai" or queue.get("program") != "my_local_ai":
        raise ValueError("wrong project")
    p1, p2, p4 = gate.get("p1"), gate.get("p2"), gate.get("p4")
    if not isinstance(p1, dict) or not isinstance(p2, dict) or not isinstance(p4, dict):
        raise ValueError("missing phase record")
    if p2.get("status") != "LOCKED":
        # No dashboard should falsely display VERIFIED in this unfinished P1 build.
        raise ValueError("P2 gate no longer matches P1-only dashboard")
    done, total = p1.get("code_req_completed"), p1.get("code_req_total")
    if type(done) is not int or type(total) is not int or total != 30 or not 0 <= done <= total:
        raise ValueError("invalid implementation metrics")
    phase = gate.get("current_phase")
    if phase not in ("P1_IMPLEMENTATION", "P0_DESIGN_AWAITING_OWNER_GO"):
        raise ValueError("unsupported dashboard phase")
    tasks = queue.get("tasks")
    if not isinstance(tasks, list) or not 0 <= len(tasks) <= 128:
        raise ValueError("invalid queue")
    statuses = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("status"), str) or not _STATE_KEY.fullmatch(task["status"]):
            raise ValueError("untrusted task status")
        statuses.append(task["status"])
    return StatusSnapshot(
        phase=phase, completed_req=done, total_req=total,
        task_total=len(tasks), ready_tasks=sum(s == "READY" for s in statuses),
        hold_tasks=sum("HOLD" in s or "BLOCKED" in s for s in statuses),
        implemented_tasks=sum(s == "IMPLEMENTED_UNVERIFIED" for s in statuses),
        owner_real_use_go=p4.get("owner_go") is True,
    )
