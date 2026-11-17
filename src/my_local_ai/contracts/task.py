"""Immutable, non-executing task contract. Guest input never grants permissions."""
from __future__ import annotations

from dataclasses import dataclass
import re

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_PLAN_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_REQ = re.compile(r"REQ-[0-9]{2}\Z")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
_FORBIDDEN_PARTS = {".git", ".env", ".ssh", ".aws", ".config", "__pycache__"}

def safe_path(path: str) -> str:
    """Lexical filter only; follow with FS symlink/reparse/ignore guard before I/O."""
    if not isinstance(path, str) or not (1 <= len(path) <= 240) or not path.isascii():
        raise ValueError("invalid relative ASCII path")
    if "\\" in path or ":" in path or any(c in path for c in "*?[]{}\"'|<>") or any(ord(c) < 32 for c in path):
        raise ValueError("unsafe path syntax")
    parts = path.split("/")
    if any(p in ("", ".", "..") or p.endswith((" ", ".")) or p.startswith(" ") for p in parts):
        raise ValueError("unsafe path segment")
    if any(p.casefold() in _FORBIDDEN_PARTS or p.casefold().split(".")[0] in _RESERVED for p in parts):
        raise ValueError("protected path")
    return path

@dataclass(frozen=True)
class ResourceBudget:
    max_calls: int
    max_seconds: int

    @classmethod
    def parse(cls, obj: object) -> "ResourceBudget":
        if not isinstance(obj, dict) or set(obj) != {"max_calls", "max_seconds"}:
            raise ValueError("resource budget keys")
        if type(obj["max_calls"]) is not int or not (1 <= obj["max_calls"] <= 100):
            raise ValueError("max_calls")
        if type(obj["max_seconds"]) is not int or not (1 <= obj["max_seconds"] <= 86400):
            raise ValueError("max_seconds")
        return cls(obj["max_calls"], obj["max_seconds"])

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    req_ids: tuple[str, ...]
    depends_on: tuple[str, ...]
    goal: str
    allowed_paths: tuple[str, ...]
    acceptance: tuple[str, ...]
    checks: tuple[tuple[str, ...], ...]
    risk: str
    resource_budget: ResourceBudget
    safety_checks: tuple[str, ...]
    plan_sha: str | None
    source_sha: str

    @classmethod
    def parse(cls, obj: object) -> "TaskSpec":
        keys = {"task_id", "req_ids", "depends_on", "goal", "allowed_paths", "acceptance", "checks", "risk", "resource_budget", "safety_checks", "plan_sha", "source_sha"}
        if not isinstance(obj, dict) or set(obj) != keys:
            raise ValueError("task schema mismatch")
        tid = obj["task_id"]
        if not isinstance(tid, str) or not _ID.fullmatch(tid):
            raise ValueError("task id")
        req, deps, paths, acceptance, checks, safety = (obj[k] for k in ("req_ids", "depends_on", "allowed_paths", "acceptance", "checks", "safety_checks"))
        if any(not isinstance(v, list) for v in (req, deps, paths, acceptance, checks, safety)):
            raise ValueError("arrays required")
        if not (1 <= len(req) <= 32 and 1 <= len(paths) <= 16 and 1 <= len(acceptance) <= 16 and len(checks) <= 16 and len(safety) <= 32):
            raise ValueError("array bound")
        if any(len({v.casefold() if isinstance(v, str) else repr(v) for v in seq}) != len(seq) for seq in (req, deps, paths, acceptance, safety)):
            raise ValueError("duplicate contract entries")
        if any(not isinstance(v, str) or not _REQ.fullmatch(v) for v in req):
            raise ValueError("invalid requirement")
        if any(not isinstance(v, str) or not _ID.fullmatch(v) or v == tid for v in deps):
            raise ValueError("invalid dependency")
        for path in paths:
            safe_path(path)
        if not isinstance(obj["goal"], str) or not (1 <= len(obj["goal"]) <= 4000):
            raise ValueError("goal")
        if any(not isinstance(v, str) or not (1 <= len(v) <= 2000) for v in acceptance):
            raise ValueError("acceptance")
        parsed_checks = []
        for argv in checks:
            if not isinstance(argv, list) or not 1 <= len(argv) <= 16:
                raise ValueError("check argv")
            if any(not isinstance(arg, str) or not 1 <= len(arg) <= 240 or any(ord(c) < 32 for c in arg) for arg in argv):
                raise ValueError("check argument")
            parsed_checks.append(tuple(argv))
        if obj["risk"] not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise ValueError("risk")
        if any(not isinstance(v, str) or not _ID.fullmatch(v) for v in safety):
            raise ValueError("safety check")
        plan_sha = obj["plan_sha"]
        if plan_sha is not None and (not isinstance(plan_sha, str) or not _PLAN_SHA.fullmatch(plan_sha)):
            raise ValueError("plan sha")
        source_sha = obj["source_sha"]
        if not isinstance(source_sha, str) or not _SHA.fullmatch(source_sha):
            raise ValueError("source sha")
        return cls(tid, tuple(req), tuple(deps), obj["goal"], tuple(paths),
                   tuple(acceptance), tuple(parsed_checks), obj["risk"],
                   ResourceBudget.parse(obj["resource_budget"]), tuple(safety), plan_sha, source_sha)
