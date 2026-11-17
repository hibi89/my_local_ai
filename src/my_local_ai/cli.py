"""Read-only MVP CLI; never invokes shell, models, network or local task execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from .contracts import PlanSpec

_ROOT = Path(__file__).resolve().parents[2]
_MAX_PLAN_BYTES = 1_048_576

def _read_json(path: Path) -> object:
    raw = path.read_bytes()
    if len(raw) > _MAX_PLAN_BYTES:
        raise ValueError("oversized JSON")
    return json.loads(raw.decode("utf-8"))

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mla", description="My Local AI read-only P1 CLI")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor", help="Read-only environment/phase checks (no network or model)")
    subs.add_parser("status", help="Read-only phase and implementation counts")
    plan = subs.add_parser("plan", help="Validate an untrusted plan (never approves it)")
    plan_sub = plan.add_subparsers(dest="plan_action", required=True)
    validate = plan_sub.add_parser("validate")
    validate.add_argument("--file", required=True, type=Path)
    queue = subs.add_parser("queue", help="Queue reports only; execution is unavailable")
    queue_sub = queue.add_subparsers(dest="queue_action", required=True)
    queue_sub.add_parser("status", help="Read-only implementation task counts")
    return parser

def _status() -> dict:
    gates = _read_json(_ROOT / "WORK_PHASE_GATES.json")
    if not isinstance(gates, dict) or gates.get("program") != "my_local_ai":
        raise ValueError("invalid local gates")
    p1, p2 = gates.get("p1"), gates.get("p2")
    if not isinstance(p1, dict) or not isinstance(p2, dict) or p2.get("status") != "LOCKED":
        raise ValueError("safety gate unavailable")
    total, done = p1.get("code_req_total"), p1.get("code_req_completed")
    if type(total) is not int or type(done) is not int or not 0 <= done <= total <= 30:
        raise ValueError("invalid local counts")
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

def _validate_plan(path: Path) -> dict:
    # Read at most 1 MiB; never print the plan or raw error details to stdout.
    with path.open("rb") as stream:
        raw = stream.read(_MAX_PLAN_BYTES + 1)
    if len(raw) > _MAX_PLAN_BYTES:
        raise ValueError("oversized plan")
    spec = PlanSpec.parse_json(raw.decode("utf-8"))
    return {
        "valid_schema": True,
        "plan_sha256": spec.digest,
        "task_count": len(spec.tasks),
        "owner_approval_verified": False,
        "execution_allowed": False,
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
        elif args.command == "queue" and args.queue_action == "status":
            payload = _queue_status()
        else:
            return 2
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"status": "HOLD", "reason": "INVALID_OR_UNAVAILABLE_LOCAL_INPUT", "execution_allowed": False}))
        return 2
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    return 0
