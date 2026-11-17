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
    approve = plan_sub.add_parser("approve", help="Owner approval request only; never signs or approves")
    approve.add_argument("--file", type=Path, required=True)
    queue = subs.add_parser("queue", help="Queue reports only; execution is unavailable")
    queue_sub = queue.add_subparsers(dest="queue_action", required=True)
    queue_sub.add_parser("status", help="Read-only implementation task counts")
    queue_sub.add_parser("next", help="P1 code-only READY IDs, never operational grants")
    start = queue_sub.add_parser("start", help="Non-executing owner HOLD; never starts a worker")
    start.add_argument("--task-id", required=True)
    start.add_argument("--plan-file", type=Path)
    start.add_argument("--state-db", type=Path)
    evidence = subs.add_parser("evidence", help="Redacted synthetic evidence, stdout only")
    evidence_sub = evidence.add_subparsers(dest="evidence_action")
    evidence_sub.add_parser("export", help="Print a sanitized evidence manifest to stdout")
    evidence_sub.add_parser("reqs", help="Source-only REQ to SWU evidence; not P2 proof")
    subs.add_parser("benchmark", help="Show synthetic fixture data, never measure real Qwen")
    stop = subs.add_parser("stop", help="Safe HOLD notice; real stop needs owner Controller")
    stop.add_argument("--task-id", required=True)
    stop.add_argument("--plan-file", type=Path)
    stop.add_argument("--state-db", type=Path)
    resume = subs.add_parser("resume", help="Safe HOLD notice; never self-resumes")
    resume.add_argument("--task-id", required=True)
    resume.add_argument("--plan-file", type=Path)
    resume.add_argument("--state-db", type=Path)
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



def _req_source_evidence() -> dict:
    """Summarize the active SWU REQ crosswalk, never treating code as verified."""
    state = _status()  # immutable local phase/legacy count check
    q = _read_json(_ROOT / "P1_SWU_TASK_QUEUE.json")
    if (not isinstance(q, dict) or q.get("policy_id") != "OWNER-SWU-HIGH-20261117"
        or q.get("program") != "my_local_ai" or q.get("p2") != "LOCKED"
        or q.get("owner_go") is not False or q.get("operational_ready") != []
        or q.get("legacy_accepted_req_count") != state["implementation_completed_req"]
        or q.get("swu_count") != 39 or q.get("req_count") != 30
        or not isinstance(q.get("tasks"), list) or len(q["tasks"]) != 39
        or not isinstance(q.get("req_mapping"), list) or len(q["req_mapping"]) != 30):
        raise ValueError("untrusted SWU evidence inventory")
    swus = {}
    for swu in q["tasks"]:
        if (not isinstance(swu, dict) or not isinstance(swu.get("id"), str)
            or not swu["id"].startswith("MLA-SWU-") or swu["id"] in swus
            or swu.get("runtime_authorization") !=
                "HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES"
            or swu.get("operational_ready") is not False
            or swu.get("code_status") not in {
                "SOURCE_COMPLETE_P2_PENDING", "IMPLEMENTED_UNVERIFIED", "READY",
                "PENDING_CODE_DEPENDENCY", "BACKLOG_READY", "BLOCKED_TRUST",
                "BLOCKED_APPROVAL", "BLOCKED_PROVENANCE", "HOLD_CODE_ATTEMPTS",
            }):
            raise ValueError("invalid source status")
        swus[swu["id"]] = swu
    rows, seen = [], set()
    for item in q["req_mapping"]:
        if (not isinstance(item, dict) or not isinstance(item.get("req_id"), str)
            or item["req_id"] in seen or not isinstance(item.get("swu_ids"), list)
            or not item["swu_ids"] or len(set(item["swu_ids"])) != len(item["swu_ids"])
            or any(sid not in swus for sid in item["swu_ids"])):
            raise ValueError("invalid REQ-SWU source mapping")
        seen.add(item["req_id"])
        source_complete = sum(
            swus[sid]["code_status"] in ("SOURCE_COMPLETE_P2_PENDING", "IMPLEMENTED_UNVERIFIED")
            for sid in item["swu_ids"]
        )
        rows.append({
            "req_id":item["req_id"], "swu_ids":item["swu_ids"],
            "source_candidate_swus":source_complete,
            "swus_total":len(item["swu_ids"]),
            "source_coverage_only":True,
        })
    if seen != {"REQ-" + f"{number:02d}" for number in range(1, 31)}:
        raise ValueError("REQ coverage incomplete")
    return {
        "req_source_rows":rows, "req_total":30, "swu_total":39,
        "implementation_completed_req":state["implementation_completed_req"],
        "p2":"LOCKED", "formal_verified_rate":"UNASSESSED",
        "independent_f18":"SECURITY_HOLD", "execution_allowed":False,
    }


def _control_hold(task_id: str, action: str) -> dict:
    queue,ids=_safe_code_queue()
    if task_id not in {task["task_id"] for task in queue["tasks"]}:
        raise ValueError("unknown target task")
    if action not in ("stop","resume","start"):
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




def _request_local_controller_action(
    *, action: str, task_id: str, plan_file: Path, state_db: Path,
) -> dict:
    """CLI -> native Controller -> MLA-owned SQLite request/HOLD.

    A stop may hold an idle task; an active lease is NEVER silently cancelled.
    Start/resume remain held requests, not an execution authority. All paths,
    plan identity, DB identity, and current task states are checked locally.
    """
    import hashlib
    import re
    import sqlite3
    from .state.sqlite_store import _write_owned_transaction

    if action not in ("start", "stop", "resume"):
        raise ValueError("invalid action")
    if not isinstance(task_id, str) or re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", task_id,
    ) is None:
        raise ValueError("invalid action task")
    _status()
    spec = PlanSpec.parse_json(_read_bounded_regular(plan_file).decode("utf-8"))
    if spec.repo != "hibi89/my_local_ai" or task_id not in {
        task.task_id for task in spec.tasks
    }:
        raise ValueError("plan not owned or task absent")
    controller = Controller(spec)  # Native MLA authority, never an EAI adapter.
    plan_task_ids = {item.task_id for item in spec.tasks}

    def persist(db):
        plan = db.execute(
            "SELECT plan_sha,blueprint_sha,state FROM plans WHERE plan_id=?",
            (spec.plan_id,),
        ).fetchone()
        if (plan is None or plan[0] != spec.digest
            or plan[1] != spec.blueprint_sha
            or plan[2] not in ("AWAITING_OWNER","APPROVED","HOLD","STOPPED")):
            raise ValueError("stale or missing Controller plan")
        rows = db.execute(
            "SELECT task_id,source_sha,state FROM tasks WHERE plan_id=?",
            (spec.plan_id,),
        ).fetchall()
        if len(rows) != len(plan_task_ids):
            raise ValueError("incomplete Controller task ledger")
        states = {}
        for tid, source_sha, state in rows:
            if (tid not in plan_task_ids or tid in states
                or source_sha != spec.blueprint_sha):
                raise ValueError("task/source drift")
            states[tid] = state
        # Controller is consulted against the ACTUAL local task ledger. No
        # untrusted VERIFIED is forwarded as independently verified evidence.
        active = db.execute(
            "SELECT task_id FROM leases WHERE plan_id=?", (spec.plan_id,),
        ).fetchall()
        active_ids = tuple(row[0] for row in active)
        if any(tid not in plan_task_ids for tid in active_ids):
            raise ValueError("untrusted lease ledger")
        decision = controller.propose(
            states, independently_verified=(), active_leases=active_ids,
        )
        if decision.execution_allowed or decision.owner_go or decision.verified:
            raise ValueError("unexpected Controller authority")
        current = states[task_id]
        if current == "VERIFIED":
            raise ValueError("cannot alter independently verified task")
        # Do not claim an active worker was stopped. Protected lease
        # cancellation and process signaling require separate signed GO.
        changed = False
        if (action == "stop" and task_id not in active_ids
            and current in {
                "QUEUED","READY","AWAITING_OWNER","BLOCKED_DEPENDENCY",
                "HOLD","INTERRUPTED",
            } and current != "HOLD"):
            update = db.execute(
                "UPDATE tasks SET state='HOLD' WHERE plan_id=? "
                "AND task_id=? AND source_sha=? AND state=?",
                (spec.plan_id,task_id,spec.blueprint_sha,current),
            )
            if update.rowcount != 1:
                raise ValueError("stale Controller task")
            changed = True
        identity = hashlib.sha256(
            ("mla-action-request/v1|" + spec.digest + "|" +
             task_id + "|" + action).encode("ascii")
        ).hexdigest()
        summary = action.upper() + "_UNTRUSTED_REQUEST_" + identity
        row = db.execute(
            "SELECT event_id FROM events WHERE plan_id=? "
            "AND event_kind='OWNER_ACTION_REQUEST_HELD' "
            "AND safe_summary=? ORDER BY event_id DESC LIMIT 1",
            (spec.plan_id, summary),
        ).fetchone()
        if row is None:
            cur = db.execute(
                "INSERT INTO events(plan_id,event_kind,safe_summary) "
                "VALUES(?,'OWNER_ACTION_REQUEST_HELD',?)",
                (spec.plan_id, summary),
            )
            event_id = cur.lastrowid
        else:
            event_id = row[0]
        return {
            "status": "HOLD",
            "action": action.upper(),
            "task_id": task_id,
            "plan_sha256": spec.digest,
            "source_sha": spec.blueprint_sha,
            "event_id": event_id,
            "controller_consulted": True,
            "action_request_recorded": True,
            "task_state_changed": changed,
            "active_lease_preserved": task_id in active_ids,
            "worker_stopped": False,
            "execution_allowed": False,
            "owner_go_verified": False,
            "independent_f18_verified": False,
            "reason": "PROTECTED_OWNER_SIGNER_AND_F18_REQUIRED",
            "p2": "LOCKED",
        }

    try:
        return _write_owned_transaction(state_db, persist)
    except sqlite3.Error:
        raise ValueError("invalid or unavailable owned Controller DB") from None


def _request_plan_approval(path: Path) -> dict:
    """Show digest for a future protected owner signer; no key and no approval."""
    spec = PlanSpec.parse_json(_read_bounded_regular(path).decode("utf-8"))
    _status()
    return {
        "status":"HOLD", "action":"PLAN_APPROVE_REQUEST_ONLY",
        "plan_sha256":spec.digest,"source_sha":spec.blueprint_sha,
        "task_count":len(spec.tasks),"owner_approval_verified":False,
        "signed_grant_created":False,"execution_allowed":False,
        "reason":"PROTECTED_OWNER_SIGNER_NOT_CONNECTED",
    }


def _benchmark_synthetic() -> dict:
    """No model, network or user data; use literal built-in fixture metadata."""
    _status()
    return {
        "mode":"SYNTHETIC_FIXTURE_ONLY",
        "sample_count":0,"measured_model_calls":0,
        "tokens_per_second":None,"accepted_req_per_hour":None,
        "real_windows":"NOT_RUN","real_qwen":"NOT_RUN",
        "p2":"LOCKED","execution_allowed":False,
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
        elif args.command == "plan" and args.plan_action == "approve":
            payload = _request_plan_approval(args.file)
            print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
            return 2
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
        elif args.command == "evidence" and args.evidence_action == "reqs":
            payload = _req_source_evidence()
        elif args.command == "evidence":
            payload = _evidence()
            if args.evidence_action == "export":
                payload = {**payload, "export_format":"REDACTED_JSON_STDOUT_ONLY",
                           "owner_go":False, "real_use_allowed":False}
        elif args.command == "benchmark":
            payload = _benchmark_synthetic()
        elif args.command == "queue" and args.queue_action == "start":
            payload = (_request_local_controller_action(action="start", task_id=args.task_id,
                       plan_file=args.plan_file, state_db=args.state_db)
                       if args.plan_file is not None and args.state_db is not None
                       else _control_hold(args.task_id, "start"))
            print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
            return 2
        elif args.command in ("stop","resume"):
            payload = (_request_local_controller_action(action=args.command, task_id=args.task_id,
                       plan_file=args.plan_file, state_db=args.state_db)
                       if args.plan_file is not None and args.state_db is not None
                       else _control_hold(args.task_id, args.command))
            print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
            return 2
        else:
            return 2
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"status": "HOLD", "reason": "INVALID_OR_UNAVAILABLE_LOCAL_INPUT", "execution_allowed": False}))
        return 2
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    return 0
