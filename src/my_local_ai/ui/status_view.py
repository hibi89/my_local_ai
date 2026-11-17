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
    code_ready_task_ids: tuple[str, ...] = ()
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
            "p1_code_ready_tasks": len(self.code_ready_task_ids),
            "p1_code_ready_ids": list(self.code_ready_task_ids),
            "hold_tasks": self.hold_tasks,
            "implemented_tasks": self.implemented_tasks,
            "p2_locked": self.p2_locked,
            "verification": self.verification,
            "owner_real_use_go": self.owner_real_use_go,
            "operation_allowed": self.operation_allowed,
            "runtime_state": "HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES",
            "provider_remote": "OFF_NOT_APPROVED",
            "optional_eai_default": "OFF",
            "optional_eai_can_grant_authority": False,
            "browser_validation": "DEFERRED_TO_P2",
        }

def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate status JSON key")
        obj[key] = value
    return obj


def _reject_nonfinite(value):
    raise ValueError("nonfinite status JSON")


def _read_limited(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError("symlink status file")
    with path.open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError("oversized status")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                      parse_constant=_reject_nonfinite)
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
    if (p1.get("status") != "IN_PROGRESS"
        or p1.get("implementation_complete_candidate") is not False
        or p1.get("high_approved_candidate") is not False
        or p4.get("owner_go") is not False):
        raise ValueError("P1 cannot claim final implementation or owner GO")
    if p2.get("status") != "LOCKED":
        # No dashboard should falsely display VERIFIED in this unfinished P1 build.
        raise ValueError("P2 gate no longer matches P1-only dashboard")
    done, total = p1.get("code_req_completed"), p1.get("code_req_total")
    if type(done) is not int or type(total) is not int or total != 30 or not 0 <= done <= total:
        raise ValueError("invalid implementation metrics")
    phase = gate.get("current_phase")
    if phase != "P1_IMPLEMENTATION":
        raise ValueError("unsupported dashboard phase")
    tasks = queue.get("tasks")
    if (queue.get("phase") != "P1_IMPLEMENTATION_ONLY"
        or queue.get("code_completed_req") != done
        or queue.get("total_code_req") != total
        or queue.get("operational_ready") != []
        or not isinstance(tasks, list) or len(tasks) != 28):
        raise ValueError("inconsistent code-only queue and phase metrics")
    statuses = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("status"), str) or not _STATE_KEY.fullmatch(task["status"]):
            raise ValueError("untrusted task status")
        if task.get("runtime_authorization") != "HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES":
            raise ValueError("unlocked runtime task in P1")
        statuses.append(task["status"])
    # P1 code authoring READY is deliberately not runtime/execution READY.
    # Treat any inconsistency as an unavailable dashboard, never grant access.
    ids = queue.get("first_ready", [])
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or len(ids) > 10:
        raise ValueError("invalid P1 code-ready list")
    if queue.get("p1_ready_mode") != "CODE_ONLY_NOT_RUNTIME":
        raise ValueError("unsupported P1 code-readiness contract")
    tasks_by_id = {task.get("task_id"):task for task in tasks}
    if (len(tasks_by_id) != len(tasks) or set(ids) != {
        task.get("task_id") for task in tasks
        if task.get("p1_code_status") == "READY_CODE_ONLY"
    }):
        raise ValueError("code ready mismatch")
    for tid in ids:
        record = tasks_by_id.get(tid)
        if (not isinstance(tid,str) or not _STATE_KEY.fullmatch(tid.replace("-","_"))
            or not isinstance(record,dict)
            or record.get("status") not in ("BLOCKED_DEPENDENCY","IMPLEMENTED_UNVERIFIED")
            or record.get("runtime_authorization") != "HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES"):
            raise ValueError("unsafe READY representation")
    return StatusSnapshot(
        phase=phase, completed_req=done, total_req=total,
        task_total=len(tasks), ready_tasks=sum(s == "READY" for s in statuses),
        hold_tasks=sum("HOLD" in s or "BLOCKED" in s for s in statuses),
        implemented_tasks=sum(s == "IMPLEMENTED_UNVERIFIED" for s in statuses),
        code_ready_task_ids=tuple(ids),
        owner_real_use_go=p4.get("owner_go") is True,
    )


@dataclass(frozen=True)
class SyntheticEvidenceSnapshot:
    source_sha: str
    run_id: int
    unit_tests: int
    mock_integration_tests: int
    security_tests: int
    status: str = "REPORTED_P1_SYNTHETIC_CI_NOT_INDEPENDENTLY_ATTESTED"
    real_windows: str = "NOT_RUN"
    f18: str = "SECURITY_HOLD"
    p2: str = "LOCKED"
    owner_go: bool = False

    def to_public_dict(self) -> dict:
        return {
            "source_sha":self.source_sha,
            "run_id":self.run_id,
            "synthetic_unit_pass":self.unit_tests,
            "synthetic_integration_pass":self.mock_integration_tests,
            "synthetic_security_pass":self.security_tests,
            "synthetic_total":sum((
                self.unit_tests,self.mock_integration_tests,self.security_tests,
            )),
            "status":self.status,
            "real_windows":self.real_windows,
            "f18":self.f18,
            "p2":self.p2,
            "owner_go":self.owner_go,
            "execution_allowed":False,
        }


def load_synthetic_evidence(project_root: str | Path) -> SyntheticEvidenceSnapshot:
    """Read bounded redacted CI metadata; *not* an independent verifier."""
    root=Path(project_root).absolute()
    load_snapshot(root)  # ensure P1/P2/owner gates remain consistent
    queue=_read_limited(root/"INSTANT_TASK_QUEUE.json")
    record=queue.get("last_p1_local_ci")
    if not isinstance(record,dict):
        raise ValueError("missing P1 evidence")
    sha,run_id=record.get("head_sha"),record.get("run_id")
    if (not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{40}",sha)
        or type(run_id) is not int or run_id<=0
        or record.get("python_compile")!="PASS"):
        raise ValueError("untrusted synthetic CI evidence")
    keys=("unit_tests_pass","synthetic_integration_tests_pass","security_contract_tests_pass")
    counts=[record.get(k) for k in keys]
    if any(type(n) is not int or not 0<=n<=100000 for n in counts):
        raise ValueError("bad synthetic count")
    if record.get("scope") not in (
        "P1_SYNTHETIC_ONLY_NOT_OWNER_WINDOWS_OS_F18",
        "P1_SYNTHETIC_ONLY_F18_WIN_OWNER_ACTUAL_NOT_RUN",
        "P1_ONLY_SYNTHETIC_NO_BROWSER_NO_REAL_MODEL_NO_WINDOWS_F18",
    ):
        raise ValueError("unsupported P1 evidence origin")
    return SyntheticEvidenceSnapshot(sha,run_id,*counts)


@dataclass(frozen=True)
class P1SourceCandidateReport:
    """Repository-evidence inventory, explicitly NOT a signed High acceptance."""
    exact_source_sha: str
    completed_swu: int
    total_swu: int
    recorded_completed_req: int
    total_req: int
    uncovered_swu_ids: tuple[str, ...]
    incomplete_req_ids: tuple[str, ...]
    missing_evidence_swu_ids: tuple[str, ...]
    source_inventory_candidate: bool
    p2_locked: bool = True

    def to_public_dict(self) -> dict:
        return {
            "source_sha": self.exact_source_sha,
            "source_swu_candidate_completed": self.completed_swu,
            "source_swu_total": self.total_swu,
            "source_swu_percent": round(100 * self.completed_swu / self.total_swu, 2),
            "official_p1_req_completed": self.recorded_completed_req,
            "official_p1_req_total": self.total_req,
            "missing_swu_ids": list(self.uncovered_swu_ids),
            "incomplete_req_ids": list(self.incomplete_req_ids),
            "missing_evidence_swu_ids": list(self.missing_evidence_swu_ids),
            "source_inventory_candidate": self.source_inventory_candidate,
            "source_sha_independently_attested": False,
            "high_approved": False,
            "p2_locked": True,
            "owner_go": False,
            "verification": "UNASSESSED",
            "runtime_authorized": False,
        }


def evaluate_p1_source_candidate(
    project_root: str | Path, *, exact_source_sha: str,
) -> P1SourceCandidateReport:
    """Join 39 source SWUs to all 30 REQs and require pinned source SHA.

    Untrusted status/queue JSON cannot unlock P2 or replace Git ancestry,
    protected F18, High acceptance, or independently verified source evidence.
    """
    if (not isinstance(exact_source_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", exact_source_sha) is None):
        raise ValueError("exact source SHA required")
    root = Path(project_root).absolute()
    current = load_snapshot(root)
    if current.operation_allowed or not current.p2_locked or current.total_req != 30:
        raise ValueError("phase gate not locked")
    gate = _read_limited(root / "WORK_PHASE_GATES.json")
    swu = _read_limited(root / "P1_SWU_TASK_QUEUE.json")
    tasks, mappings = swu.get("tasks"), swu.get("req_mapping")
    if (swu.get("program") != "my_local_ai"
        or swu.get("policy_id") != "OWNER-SWU-HIGH-20261117"
        or swu.get("stage") != "P1_FUNCTION_CODE_ONLY"
        or swu.get("swu_count") != 39 or swu.get("req_count") != 30
        or swu.get("owner_go") is not False
        or swu.get("operational_ready") != []
        or swu.get("f18") != "SECURITY_HOLD"
        or swu.get("p2") != "LOCKED"
        or not isinstance(tasks, list) or len(tasks) != 39
        or not isinstance(mappings, list) or len(mappings) != 30
        or gate["p1"].get("high_approved_candidate") is not False):
        raise ValueError("invalid P1 source inventory")
    last = swu.get("last_source_wave")
    if (not isinstance(last, dict)
        or last.get("source_sha") != exact_source_sha):
        raise ValueError("source SHA differs from recorded code wave")
    by_id = {}
    incomplete, missing_evidence = [], []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("invalid source task")
        tid = task.get("id")
        if (not isinstance(tid, str) or re.fullmatch(r"MLA-SWU-\d{3}", tid) is None
            or tid in by_id
            or task.get("runtime_authorization")
                != "HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES"
            or task.get("operational_ready") is not False
            or task.get("owner_go") is not False):
            raise ValueError("unsafe source task record")
        by_id[tid] = task
        if task.get("code_status") != "SOURCE_COMPLETE_P2_PENDING":
            incomplete.append(tid)
            continue
        sha = task.get("latest_code_sha")
        legacy = task.get("evidence_sha_by_legacy")
        if (not isinstance(sha, str) or
            re.fullmatch(r"[0-9a-f]{40}", sha) is None):
            if (not isinstance(legacy, dict) or not legacy
                or any(not isinstance(x, str)
                       or re.fullmatch(r"[0-9a-f]{40}", x) is None
                       for x in legacy.values())):
                missing_evidence.append(tid)
    if len(by_id) != 39 or {f"MLA-SWU-{n:03d}" for n in range(1, 40)} != set(by_id):
        raise ValueError("source SWU ID mismatch")
    incomplete_req, req_seen = [], set()
    for rec in mappings:
        if not isinstance(rec, dict):
            raise ValueError("invalid requirement mapping")
        req, covered = rec.get("req_id"), rec.get("swu_ids")
        if (not isinstance(req, str)
            or re.fullmatch(r"REQ-\d{2}", req) is None
            or req in req_seen or not isinstance(covered, list)
            or not covered or len(covered) != len(set(covered))
            or any(x not in by_id or req not in by_id[x].get("req_ids", [])
                   for x in covered)):
            raise ValueError("inconsistent SWU/REQ mapping")
        req_seen.add(req)
        if any(x in incomplete or x in missing_evidence for x in covered):
            incomplete_req.append(req)
    if req_seen != {f"REQ-{n:02d}" for n in range(1, 31)}:
        raise ValueError("missing REQ inventory")
    completed = 39 - len(incomplete)
    if (swu.get("source_complete_swu_count") != completed
        or swu.get("source_incomplete_swu_count") != len(incomplete)
        or swu.get("legacy_accepted_req_count") != current.completed_req):
        raise ValueError("source counters are inconsistent")
    return P1SourceCandidateReport(
        exact_source_sha, completed, 39, current.completed_req, 30,
        tuple(incomplete), tuple(incomplete_req), tuple(missing_evidence),
        not incomplete and not missing_evidence and not incomplete_req,
    )
