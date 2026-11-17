"""Canonical PlanSpec; parsing an approval claim NEVER grants execution authority."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from .task import TaskSpec

def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result

def canonical_digest(value: object) -> str:
    """Canonical UTF-8 JSON digest. Never a signature or owner consent."""
    data = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class PlanSpec:
    plan_id: str
    repo: str
    branch: str
    blueprint_sha: str
    tasks: tuple[TaskSpec, ...]
    digest: str
    approval_scope_claim: str
    approval_status_claim: str
    approved: bool = False  # actual owner-consent verification is a separate trust boundary

    @classmethod
    def parse_json(cls, raw: str) -> "PlanSpec":
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > 1_048_576:
            raise ValueError("plan size")
        obj = json.loads(
            raw, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON"))
        )
        if not isinstance(obj, dict) or set(obj) != {"version", "plan_id", "blueprint", "approval", "tasks"}:
            raise ValueError("plan schema")
        if type(obj["version"]) is not int or obj["version"] != 1:
            raise ValueError("unsupported plan version")
        bp = obj["blueprint"]
        if not isinstance(bp, dict) or set(bp) != {"repo", "branch", "sha"}:
            raise ValueError("blueprint schema")
        if not isinstance(obj["plan_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", obj["plan_id"]):
            raise ValueError("plan id")
        if not isinstance(bp["repo"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", bp["repo"]):
            raise ValueError("repo")
        if not isinstance(bp["branch"], str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,128}", bp["branch"]):
            raise ValueError("branch")
        if (".." in bp["branch"] or "//" in bp["branch"] or bp["branch"].startswith(("/", "-", "."))
            or bp["branch"].endswith(("/", ".")) or ".lock" in bp["branch"].lower()):
            raise ValueError("unsafe branch")
        if not isinstance(bp["sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", bp["sha"]):
            raise ValueError("blueprint sha")
        if not isinstance(obj["tasks"], list) or not 1 <= len(obj["tasks"]) <= 256:
            raise ValueError("task count")
        tasks = tuple(TaskSpec.parse(t) for t in obj["tasks"])
        ids = [t.task_id for t in tasks]
        known = set(ids)
        if len(known) != len(ids) or any(not set(t.depends_on).issubset(known) for t in tasks):
            raise ValueError("duplicate task or unknown dependency")
        if any(t.source_sha != bp["sha"] for t in tasks):
            raise ValueError("source baseline mismatch")
        graph = {t.task_id: t.depends_on for t in tasks}
        active, done = set(), set()
        def visit(node):
            if node in active:
                raise ValueError("dependency cycle")
            if node in done:
                return
            active.add(node)
            for dependency in graph[node]:
                visit(dependency)
            active.remove(node)
            done.add(node)
        for node in graph:
            visit(node)

        claim = obj["approval"]
        if not isinstance(claim, dict) or set(claim) != {"status", "scope", "digest"}:
            raise ValueError("approval claim schema")
        if claim["status"] not in ("NOT_APPROVED", "APPROVED"):
            raise ValueError("approval claim status")
        if not isinstance(claim["scope"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", claim["scope"]):
            raise ValueError("approval scope")
        # Excluding approval and replacing task.plan_sha with null prevents circular hashing.
        identity = {
            "version": 1, "plan_id": obj["plan_id"], "blueprint": bp,
            "tasks": [{**t, "plan_sha": None} for t in obj["tasks"]]
        }
        digest = canonical_digest(identity)
        if any(t.plan_sha not in (None, digest) for t in tasks):
            raise ValueError("stale task plan_sha")
        if claim["status"] == "NOT_APPROVED":
            if claim["digest"] is not None:
                raise ValueError("unauthorized approval digest")
        else:
            scope_digest = canonical_digest({"plan_sha": digest, "scope": claim["scope"]})
            if claim["digest"] != scope_digest or any(t.plan_sha != digest for t in tasks):
                raise ValueError("approval claim inconsistent with plan")
        # A self-declared matching digest is not an owner signature or an authorization.
        return cls(obj["plan_id"], bp["repo"], bp["branch"], bp["sha"], tasks,
                   digest, claim["scope"], claim["status"], False)
