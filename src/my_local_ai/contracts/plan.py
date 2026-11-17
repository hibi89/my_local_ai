"""Canonical plan parsing; approval is deliberately NOT conferred by parsing."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import re
from .task import TaskSpec

def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj

def canonical_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class PlanSpec:
    plan_id: str
    repo: str
    branch: str
    blueprint_sha: str
    tasks: tuple[TaskSpec, ...]
    digest: str
    approved: bool = False  # external owner consent must be verified separately

    @classmethod
    def parse_json(cls, raw: str) -> "PlanSpec":
        obj = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if not isinstance(obj, dict) or set(obj) != {"version", "plan_id", "blueprint", "tasks"} or obj["version"] != 1 or isinstance(obj["version"], bool):
            raise ValueError("plan schema")
        bp = obj["blueprint"]
        if not isinstance(bp, dict) or set(bp) != {"repo", "branch", "sha"}:
            raise ValueError("blueprint")
        if not isinstance(obj["plan_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", obj["plan_id"]):
            raise ValueError("plan id")
        if not isinstance(bp["repo"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", bp["repo"]):
            raise ValueError("repo")
        if not isinstance(bp["branch"], str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,128}", bp["branch"]) or ".." in bp["branch"] or bp["branch"].startswith(("/", "-")) or bp["branch"].endswith(("/", ".")):
            raise ValueError("branch")
        if not isinstance(bp["sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", bp["sha"]):
            raise ValueError("blueprint sha")
        if not isinstance(obj["tasks"], list) or not obj["tasks"]:
            raise ValueError("tasks")
        tasks = tuple(TaskSpec.parse(t) for t in obj["tasks"])
        ids = {t.task_id for t in tasks}
        if len(ids) != len(tasks) or any(not set(t.depends_on) <= ids for t in tasks):
            raise ValueError("duplicate or unknown dependency")
        graph = {t.task_id: t.depends_on for t in tasks}
        visiting, visited = set(), set()
        def visit(node):
            if node in visiting:
                raise ValueError("dependency cycle")
            if node in visited:
                return
            visiting.add(node)
            for dep in graph[node]:
                visit(dep)
            visiting.remove(node)
            visited.add(node)
        for node in graph:
            visit(node)
        return cls(obj["plan_id"], bp["repo"], bp["branch"], bp["sha"], tasks, canonical_digest(obj))
