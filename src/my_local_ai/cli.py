"""Read-only MVP CLI; never invokes shell, models, network or local task execution."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import shutil
import sys

from .contracts import PlanSpec
from .controller.decision import Controller

_ROOT = Path(__file__).resolve().parents[2]
_MAX_PLAN_BYTES = 1_048_576

def _read_bounded_regular(path: Path) -> bytes:
    """Read a bounded regular file without following link/reparse ancestors.

    This is a host-level read-only preflight, not a Windows owner ACL claim.
    A hostile simultaneous filesystem writer remains outside P1 trust guarantees.
    """
    candidate = Path(path).absolute()
    for segment in (candidate, *candidate.parents):
        info = segment.lstat()
        if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) &
               getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise ValueError("unsafe state/plan file alias")
    before = candidate.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
        or before.st_size > _MAX_PLAN_BYTES):
        raise ValueError("nonregular or oversized local file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(candidate, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError("local file replaced before read")
        raw = stream.read(_MAX_PLAN_BYTES + 1)
    after = candidate.lstat()
    if ((after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_size != len(raw) or len(raw) > _MAX_PLAN_BYTES):
        raise ValueError("local file changed while reading")
    return raw


def _read_json(path: Path) -> object:
    return json.loads(_read_bounded_regular(path).decode("utf-8"))

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mla", description="My Local AI read-only P1 CLI")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor", help="Read-only environment/phase checks (no network or model)")
    subs.add_parser("status", help="Read-only phase and implementation counts")
    plan = subs.add_parser("plan", help="Validate an untrusted plan (never approves it)")
    plan_sub = plan.add_subparsers(dest="plan_action", required=True)
    validate = plan_sub.add_parser("validate")
    validate.add_argument("--file", required=True, type=Path)
    preview = plan_sub.add_parser("preview", help="Offline, non-executing Controller batch preview")
    preview.add_argument("--file", required=True, type=Path)
    preview.add_argument("--max-tasks", type=int, default=8)
    preview.add_argument("--max-calls", type=int, default=8)
    preview.add_argument("--max-seconds", type=int, default=600)
    preview.add_argument("--eai-file", type=Path, default=None,
                         help="Optional pinned offline EAI data envelope, never a model call")
    queue = subs.add_parser("queue", help="Queue reports only; execution is unavailable")
    queue_sub = queue.add_subparsers(dest="queue_action", required=True)
    queue_sub.add_parser("status", help="Read-only implementation task counts")
    queue_sub.add_parser("next", help="P1 code-only READY IDs, never operational grants")
    subs.add_parser("evidence", help="Display redacted P1 synthetic evidence only")
    stop = subs.add_parser("stop", help="Safe HOLD notice; real stop needs owner Controller")
    stop.add_argument("--task-id", required=True)
    resume = subs.add_parser("resume", help="Safe HOLD notice; never self-resumes")
    resume.add_argument("--task-id", required=True)
    return parser

def _status() -> dict:
    gates = _read_json(_ROOT / "WORK_PHASE_GATES.json")
    if not isinstance(gates, dict) or gates.get("program") != "my_local_ai":
        raise ValueError("invalid local gates")
    p1, p2 = gates.get("p1"), gates.get("p2")
    p4 = gates.get("p4")
    if (not isinstance(p1, dict) or not isinstance(p2, dict)
        or not isinstance(p4, dict) or gates.get("current_phase") != "P1_IMPLEMENTATION"
        or p1.get("status") != "IN_PROGRESS"
        or p1.get("implementation_complete_candidate") is not False
        or p1.get("high_approved_candidate") is not False
        or p2.get("status") != "LOCKED" or p2.get("verified_rate") != "UNASSESSED"
        or p4.get("owner_go") is not False):
        raise ValueError("safety gate unavailable")
    total, done = p1.get("code_req_total"), p1.get("code_req_completed")
    if type(total) is not int or type(done) is not int or total != 30 or not 0 <= done < total:
        raise ValueError("invalid local counts")
    queue = _read_json(_ROOT / "INSTANT_TASK_QUEUE.json")
    if (not isinstance(queue, dict) or queue.get("program") != "my_local_ai"
        or queue.get("phase") != "P1_IMPLEMENTATION_ONLY"
        or queue.get("p1_ready_mode") != "CODE_ONLY_NOT_RUNTIME"
        or queue.get("operational_ready") != []
        or queue.get("code_completed_req") != done
        or queue.get("total_code_req") != total
        or not isinstance(queue.get("tasks"), list) or len(queue["tasks"]) != 28):
        raise ValueError("queue and phase mismatch")
    rows = queue["tasks"]
    if (any(not isinstance(t, dict) or not isinstance(t.get("task_id"), str)
            or t.get("runtime_authorization") !=
               "HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES" for t in rows)
        or len({t["task_id"] for t in rows}) != 28):
        raise ValueError("untrusted code-only queue")
    ready = queue.get("first_ready")
    if (not isinstance(ready, list) or not 0 < len(ready) <= 10
        or len(ready) != len(set(ready))
        or set(ready) != {t["task_id"] for t in rows
                           if t.get("p1_code_status") == "READY_CODE_ONLY"}):
        raise ValueError("code-only READY mismatch")
    return {
        "program": "my_local_ai",
        "phase": gates.get("current_phase"),
        "implementation_completed_req": done,
        "implementation_total_req": total,
        "p2": "LOCKED",
        "verified_rate": "UNASSESSED",
        "execution_allowed": False,
    }

def _queue_status() -> dict:
    state = _status()
    queue = _read_json(_ROOT / "INSTANT_TASK_QUEUE.json")
    if not isinstance(queue, dict) or not isinstance(queue.get("tasks"), list):
        raise ValueError("queue schema")
    counts: dict[str, int] = {}
    for task in queue["tasks"]:
        if not isinstance(task, dict) or not isinstance(task.get("status"), str):
            raise ValueError("malformed queue")
        key = task["status"]
        counts[key] = counts.get(key, 0) + 1
    return {**state, "task_counts": counts, "tasks_total": len(queue["tasks"])}

def _safe_code_queue() -> tuple[dict, list[str]]:
    queue=_read_json(_ROOT / "INSTANT_TASK_QUEUE.json")
    if (not isinstance(queue, dict) or queue.get("program")!="my_local_ai"
        or queue.get("p1_ready_mode")!="CODE_ONLY_NOT_RUNTIME"
        or queue.get("operational_ready")!=[]
        or not isinstance(queue.get("tasks"),list)):
        raise ValueError("unsafe code-only queue")
    rows=queue["tasks"]
    by_id={}
    for task in rows:
        if (not isinstance(task,dict) or not isinstance(task.get("task_id"),str)
            or task["task_id"] in by_id
            or task.get("runtime_authorization")!="HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES"):
            raise ValueError("unsafe queue task")
        by_id[task["task_id"]]=task
    ids=queue.get("first_ready")
    if (not isinstance(ids,list) or not 0<len(ids)<=10 or len(set(ids))!=len(ids)
        or set(ids)!={t["task_id"] for t in rows
                      if t.get("p1_code_status")=="READY_CODE_ONLY"}):
        raise ValueError("inconsistent code ready")
    if any(
        tid not in by_id
        or by_id[tid].get("status") not in ("BLOCKED_DEPENDENCY","IMPLEMENTED_UNVERIFIED")
        for tid in ids
    ):
        raise ValueError("unapproved P1 code task")
    return queue,ids


def _queue_next() -> dict:
    queue,ids=_safe_code_queue()
    return {
        **_status(),
        "p1_code_ready_ids":ids,
        "p1_code_ready_count":len(ids),
        "operational_ready_count":0,
        "code_only":True,
        "action": "AUTHOR_SOURCE_ONLY",
        "owner_go":False,
    }


def _evidence() -> dict:
    queue,_=_safe_code_queue()
    record=queue.get("last_p1_local_ci")
    if not isinstance(record,dict):
        raise ValueError("missing synthetic CI evidence")
    sha=record.get("head_sha")
    run_id=record.get("run_id")
    keys=("unit_tests_pass","synthetic_integration_tests_pass","security_contract_tests_pass")
    if (not isinstance(sha,str) or len(sha)!=40
        or any(ch not in "0123456789abcdef" for ch in sha)
        or type(run_id) is not int or run_id<=0
        or any(type(record.get(k)) is not int or record[k]<0 for k in keys)):
        raise ValueError("invalid evidence")
    return {
        "source_sha":sha,
        "run_id":run_id,
        "synthetic_unit":record["unit_tests_pass"],
        "synthetic_integration":record["synthetic_integration_tests_pass"],
        "synthetic_security":record["security_contract_tests_pass"],
        "p2":"LOCKED","formal_verified_rate":"UNASSESSED",
        "real_windows":"NOT_RUN","independent_f18":"SECURITY_HOLD",
        "execution_allowed":False,
    }


def _control_hold(task_id: str, action: str) -> dict:
    queue,ids=_safe_code_queue()
    if task_id not in {task["task_id"] for task in queue["tasks"]}:
        raise ValueError("unknown target task")
    if action not in ("stop","resume"):
        raise ValueError("unsupported action")
    # P1 CLI must not attempt runtime state writes, signal processes,
    # remove leases or bypass the protected owner-controlled Controller.
    return {
        "status":"HOLD",
        "action":action.upper(),
        "task_id":task_id,
        "reason":"PROTECTED_OWNER_CONTROLLER_NOT_CONNECTED",
        "task_state_changed":False,
        "execution_allowed":False,
        "p2":"LOCKED",
    }


def _validate_plan(path: Path) -> dict:
    # Read at most 1 MiB; never print the plan or raw error details to stdout.
    spec = PlanSpec.parse_json(_read_bounded_regular(path).decode("utf-8"))
    return {
        "valid_schema": True,
        "plan_sha256": spec.digest,
        "task_count": len(spec.tasks),
        "owner_approval_verified": False,
        "execution_allowed": False,
    }

def _preview_plan(
    path: Path, *, max_tasks: int, max_calls: int, max_seconds: int,
    optional_eai_file: Path | None = None,
) -> dict:
    """Purely local P1 dry-run: plan schema cannot mint owner approval."""
    _status()  # P1-only phase/queue safety check before reading untrusted plan
    plan = PlanSpec.parse_json(_read_bounded_regular(path).decode("utf-8"))
    # A guest's VERIFIED labels never stand in for trusted F18 results.
    # Without actual protected verification, only DAG roots can be proposed.
    states = {task.task_id: "READY" for task in plan.tasks}
    optional = (
        _read_bounded_regular(optional_eai_file).decode("utf-8")
        if optional_eai_file is not None else None
    )
    batch = Controller(plan).propose_code_batch(
        states, max_tasks=max_tasks, max_total_calls=max_calls,
        max_total_seconds=max_seconds,
        independently_verified=(), active_leases=(),
        optional_eai_envelope_json=optional,
    )
    if (batch.runnable or batch.owner_go_verified
        or batch.independent_f18_verified or batch.model_calls_executed
        or batch.state != "CODE_CANDIDATE_ONLY"):
        raise ValueError("unsafe non-executing preview")
    return {
        "plan_sha256": batch.plan_sha256,
        "source_sha": batch.source_sha,
        "candidate_task_ids": list(batch.task_ids),
        "deferred": [{"task_id": tid, "reason": reason}
                     for tid, reason in batch.deferred],
        "reserved_calls_max": batch.reserved_calls,
        "reserved_seconds_max": batch.reserved_seconds,
        "advisor_status": batch.advisory_status,
        "plan_approval": "NOT_VERIFIED",
        "model_calls_executed": 0,
        "independent_f18": "SECURITY_HOLD",
        "p2": "LOCKED",
        "execution_allowed": False,
        "git_write_allowed": False,
        "code_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            payload = {
                "python_3_11_or_newer": sys.version_info >= (3, 11),
                "git_on_path": shutil.which("git") is not None,
                **_status(),
                "actual_ollama_probe": "NOT_RUN",
                "actual_windows_isolation": "NOT_RUN",
            }
        elif args.command == "status":
            payload = _status()
        elif args.command == "plan" and args.plan_action == "validate":
            payload = _validate_plan(args.file)
        elif args.command == "plan" and args.plan_action == "preview":
            payload = _preview_plan(
                args.file, max_tasks=args.max_tasks,
                max_calls=args.max_calls, max_seconds=args.max_seconds,
                optional_eai_file=args.eai_file,
            )
        elif args.command == "queue" and args.queue_action == "status":
            payload = _queue_status()
        elif args.command == "queue" and args.queue_action == "next":
            payload = _queue_next()
        elif args.command == "evidence":
            payload = _evidence()
        elif args.command in ("stop","resume"):
            payload = _control_hold(args.task_id, args.command)
            print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
            return 2
        else:
            return 2
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"status": "HOLD", "reason": "INVALID_OR_UNAVAILABLE_LOCAL_INPUT", "execution_allowed": False}))
        return 2
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    return 0
