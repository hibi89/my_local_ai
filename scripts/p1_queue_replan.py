"""P1 queue-code readiness guard: source authoring is NOT execution authorization.

Run against INSTANT_TASK_QUEUE.json for safe deterministic task-wave checks.
Never issues owner GO or changes task state, external services, source files,
protected branches, CI settings or P2 state.
"""
from __future__ import annotations
import json
from pathlib import Path

EXPECTED = frozenset({
    "MLA-001","MLA-002","MLA-003","MLA-004","MLA-005","MLA-006",
    "MLA-007","MLA-008","MLA-009","MLA-010","MLA-011","MLA-012",
    "MLA-013","MLA-014","MLA-015","MLA-016","MLA-017","MLA-018",
    "MLA-019","MLA-020","MLA-021","MLA-022","MLA-023","MLA-024",
    "MLA-025","MLA-028","MLA-029","MLA-030",
})
RUNTIME_DEPENDS_ON = {
    "MLA-001": [],
    "MLA-002": [],
    "MLA-003": [],
    "MLA-004": [],
    "MLA-005": [],
    "MLA-006": ["MLA-002"],
    "MLA-007": ["MLA-002"],
    "MLA-008": ["MLA-001","MLA-002"],
    "MLA-009": ["MLA-002","MLA-007"],
    "MLA-010": ["MLA-002","MLA-007"],
    "MLA-011": ["MLA-010"],
    "MLA-012": ["MLA-005","MLA-011"],
    "MLA-013": ["MLA-012"],
    "MLA-014": ["MLA-001","MLA-002","MLA-003"],
    "MLA-015": ["MLA-003","MLA-004","MLA-014"],
    "MLA-016": ["MLA-010","MLA-015"],
    "MLA-017": ["MLA-007","MLA-010","MLA-014"],
    "MLA-018": ["MLA-014","MLA-015","MLA-017"],
    "MLA-019": ["MLA-006","MLA-008","MLA-010","MLA-013","MLA-016","MLA-018"],
    "MLA-020": ["MLA-005","MLA-012"],
    "MLA-021": ["MLA-006","MLA-007"],
    "MLA-022": ["MLA-017","MLA-019","MLA-020"],
    "MLA-023": ["MLA-009","MLA-018"],
    "MLA-024": ["MLA-023"],
    "MLA-025": ["MLA-019","MLA-021","MLA-022","MLA-029"],
    "MLA-028": ["MLA-008","MLA-015"],
    "MLA-029": ["MLA-015","MLA-019"],
    "MLA-030": ["MLA-004","MLA-014","MLA-015"],
}
MUST_HOLD = frozenset({"MLA-001","MLA-003","MLA-009"})
CODE_READY = "READY_CODE_ONLY"
RUNTIME_HOLD = "HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES"
ALLOWED_CODE_STATUSES = frozenset({
    CODE_READY, "PENDING_CODE_DEPENDENCY",
    "IMPLEMENTED_UNVERIFIED", "BLOCKED_PROVENANCE",
})


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def audit_p1_queue(raw: str) -> dict:
    queue = json.loads(raw, object_pairs_hook=_unique_pairs)
    if not isinstance(queue, dict) or queue.get("program") != "my_local_ai":
        raise ValueError("unrecognized program")
    if (queue.get("task_count") != 28 or queue.get("total_code_req") != 30
        or type(queue.get("code_completed_req")) is not int
        or not 0 <= queue["code_completed_req"] < 30
        or queue.get("phase") != "P1_IMPLEMENTATION_ONLY"
        or queue.get("p1_ready_mode") != "CODE_ONLY_NOT_RUNTIME"
        or queue.get("operational_ready") != []):
        raise ValueError("P1 invariant or runtime availability invalid")
    replan = queue.get("p1_implementation_replan")
    if (not isinstance(replan, dict) or replan.get("version") != 1
        or replan.get("source_rights") != "NO_ORIGINAL_SOURCE_IMPORT"
        or replan.get("protected_owner_signer") != "HOLD"
        or replan.get("independent_f18") != "HOLD"
        or replan.get("git_promotion") != "HOLD"
        or replan.get("p2") != "LOCKED"
        or replan.get("code_req_denominator") != 30):
        raise ValueError("unapproved safety-gate changes")
    tasks = queue.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 28:
        raise ValueError("task inventory mismatch")
    by_id = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("task schema")
        tid = task.get("task_id")
        if tid not in EXPECTED or tid in by_id:
            raise ValueError("duplicate/unknown task")
        by_id[tid] = task
        if (task.get("runtime_authorization") != RUNTIME_HOLD
            or task.get("runtime_dependencies_preserved") is not True
            or task.get("p1_code_status") not in ALLOWED_CODE_STATUSES):
            raise ValueError("runtime gate/code status invalid")
        deps = task.get("p1_code_depends_on")
        if (not isinstance(deps, list) or len(deps) != len(set(deps))
            or any(dep not in EXPECTED or dep == tid for dep in deps)):
            raise ValueError("bad code dependency")
        if task.get("depends_on") != RUNTIME_DEPENDS_ON[tid]:
            raise ValueError("full acceptance dependency graph modified")
        if (not isinstance(task.get("depends_on"), list)
            or not set(deps).issubset(set(task["depends_on"]))):
            raise ValueError("source dependency cannot invent old edge")
        if tid in MUST_HOLD and task.get("p1_code_status") == CODE_READY:
            raise ValueError("must preserve provenance/trust blockers")
        if task.get("p1_code_status") == CODE_READY:
            if (task.get("status") not in {"BLOCKED_DEPENDENCY", "IMPLEMENTED_UNVERIFIED"}
                or task.get("p1_code_blockers") != []):
                raise ValueError("runtime task cannot be marked executable")
        if task.get("status") == "BLOCKED_PROVENANCE" and task.get("p1_code_status") != "BLOCKED_PROVENANCE":
            raise ValueError("source rights still pending")
    if set(by_id) != EXPECTED:
        raise ValueError("missing task")
    visiting, visited = set(), set()
    def visit(tid: str) -> None:
        if tid in visiting:
            raise ValueError("code dependency cycle")
        if tid in visited:
            return
        visiting.add(tid)
        for dep in by_id[tid]["p1_code_depends_on"]:
            visit(dep)
        visiting.remove(tid)
        visited.add(tid)
    for tid in EXPECTED:
        visit(tid)
    ready = queue.get("first_ready")
    if (not isinstance(ready, list) or len(ready) != len(set(ready))
        or not 0 < len(ready) <= 10
        or set(ready) != {t for t,v in by_id.items() if v["p1_code_status"] == CODE_READY}):
        raise ValueError("code READY mismatches status")
    for tid in ready:
        if not all(by_id[dep].get("evidence_sha") is not None for dep in by_id[tid]["p1_code_depends_on"]):
            raise ValueError("source module dependency has no code evidence")
    return {
        "status": "SAFE_CODE_QUEUE_ONLY",
        "p1_code_ready": tuple(ready),
        "runtime_actions_authorized": 0,
        "unblocked_provenance": False,
        "independent_f18_proven": False,
        "p2_locked": True,
        "completed_req": queue["code_completed_req"],
        "req_denominator": 30,
    }


def main() -> int:
    path = Path(__file__).resolve().parents[1] / "INSTANT_TASK_QUEUE.json"
    result = audit_p1_queue(path.read_text(encoding="utf-8"))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
