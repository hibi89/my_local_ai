"""Immutable, non-executing task contract. No model-provided authority."""
from __future__ import annotations
from dataclasses import dataclass
import re

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_REQ = re.compile(r"REQ-[0-9]{2}\Z")

def safe_path(path: str) -> str:
    if not isinstance(path, str) or not path or len(path) > 240:
        raise ValueError("invalid path")
    if not path.isascii() or "\\" in path or ":" in path or any(c in path for c in "*?[]{}"):
        raise ValueError("unsafe path")
    parts = path.split("/")
    if any(p in ("", ".", "..") or p.endswith((" ", ".")) for p in parts):
        raise ValueError("unsafe path segment")
    if any(p.lower() in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1,10)), *(f"lpt{i}" for i in range(1,10))} for p in parts):
        raise ValueError("reserved path")
    return path

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    req_ids: tuple[str, ...]
    depends_on: tuple[str, ...]
    goal: str
    allowed_paths: tuple[str, ...]
    source_sha: str

    @classmethod
    def parse(cls, obj: dict) -> "TaskSpec":
        if not isinstance(obj, dict) or set(obj) != {"task_id", "req_ids", "depends_on", "goal", "allowed_paths", "source_sha"}:
            raise ValueError("task fields")
        tid = obj["task_id"]
        if not isinstance(tid, str) or not _ID.fullmatch(tid):
            raise ValueError("task id")
        req, deps, paths = (obj[k] for k in ("req_ids", "depends_on", "allowed_paths"))
        if any(not isinstance(v, list) for v in (req, deps, paths)):
            raise ValueError("arrays required")
        if not req or not 1 <= len(paths) <= 16 or len(set(req)) != len(req) or len(set(deps)) != len(deps) or len(set(paths)) != len(paths):
            raise ValueError("empty or duplicate entries")
        if any(not isinstance(r, str) or not _REQ.fullmatch(r) for r in req):
            raise ValueError("req id")
        if any(not isinstance(d, str) or not _ID.fullmatch(d) or d == tid for d in deps):
            raise ValueError("dependency")
        for path in paths:
            safe_path(path)
        if not isinstance(obj["goal"], str) or not 1 <= len(obj["goal"]) <= 4000:
            raise ValueError("goal")
        if not isinstance(obj["source_sha"], str) or not _SHA.fullmatch(obj["source_sha"]):
            raise ValueError("source sha")
        return cls(tid, tuple(req), tuple(deps), obj["goal"], tuple(paths), obj["source_sha"])
