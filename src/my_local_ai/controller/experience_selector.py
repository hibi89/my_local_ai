"""Optional MESA Controller selection, bounded advice after native READY.

This is the caller-to-callee for MESA indexed retrieval. It only adjusts
ties among already-eligible tasks and cannot write plans, run tasks, call
models, obtain grants or promote source.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3

from my_local_ai.contracts.plan import PlanSpec
from my_local_ai.controller.decision import Controller
from my_local_ai.experience.retrieval import search_experiences


@dataclass(frozen=True, slots=True)
class MESAControllerProposal:
    plan_sha256: str
    source_git_sha: str
    candidate_task_ids: tuple[str, ...]
    experience_refs: tuple[str, ...]
    status: str
    execution_allowed: bool = False
    owner_go: bool = False
    independent_f18_verified: bool = False
    git_write_allowed: bool = False

    def __post_init__(self) -> None:
        if any(getattr(self, flag) is not False for flag in (
            "execution_allowed", "owner_go",
            "independent_f18_verified", "git_write_allowed",
        )):
            raise ValueError("advice cannot mint controller authority")


def select_with_experience(
    *, plan_json: str, protected_states: dict[str, str],
    experience_conn: sqlite3.Connection | None = None,
    enabled: bool = False, project_id: str,
    scope_ref: str, rights_tag: str,
    environment_digest: str | None = None,
    task_error_fingerprints: dict[str, str] | None = None,
    active_leases: tuple[str, ...] = (),
) -> MESAControllerProposal:
    """Return only non-executing READY proposals with safe optional hints.

    Independently verified dependencies are NEVER inferred from memory.
    The normal Controller DAG is computed first. Unknown memory/SQLite
    errors or disabled MESA preserve the original Qwen ordering.
    """
    plan = PlanSpec.parse_json(plan_json)
    controller = Controller(plan)
    baseline = controller.propose(
        protected_states, independently_verified=(), active_leases=active_leases,
    )
    if baseline.owner_go or baseline.verified or baseline.execution_allowed:
        raise ValueError("unsafe native Controller result")
    baseline_ids = tuple(d.task_id for d in baseline.decisions)
    status = "OFF" if not enabled else "NO_VALID_MEMORY"
    refs: list[str] = []
    ranked: set[str] = set()
    if enabled and experience_conn is not None and task_error_fingerprints:
        if not isinstance(task_error_fingerprints, dict) or len(task_error_fingerprints) > 256:
            raise ValueError("invalid task memory request")
        # Query only tasks already admitted to the immutable Controller DAG.
        for candidate in baseline.decisions:
            fingerprint = task_error_fingerprints.get(candidate.task_id)
            if fingerprint is None or len(refs) >= 3:
                continue
            try:
                hints = search_experiences(
                    experience_conn, project_id=project_id,
                    plan_sha256=plan.digest, source_git_sha=candidate.source_sha,
                    scope_ref=scope_ref, rights_tag=rights_tag,
                    error_fingerprint=fingerprint, enabled=True,
                    environment_digest=environment_digest,
                    max_results=3-len(refs),
                )
            except (sqlite3.Error, ValueError, TypeError, RuntimeError):
                # Optional MESA input/store failures cannot take down the
                # original local Qwen Controller or make a task executable.
                return MESAControllerProposal(
                    plan.digest, plan.blueprint_sha, baseline_ids, (),
                    "MEMORY_UNAVAILABLE_FALLBACK",
                )
            if hints:
                ranked.add(candidate.task_id)
                for hint in hints:
                    for ref in hint.record_ids:
                        if ref not in refs:
                            refs.append(ref)
                            if len(refs) == 3:
                                break
        if ranked:
            advisory = json.dumps({
                "version": 1,
                "hints": [{"task_id": task_id, "rank": 0}
                          for task_id in sorted(ranked)],
            }, sort_keys=True, separators=(",", ":"))
            try:
                changed = controller.propose(
                    protected_states, independently_verified=(),
                    active_leases=active_leases, advisory_json=advisory,
                )
                after = tuple(d.task_id for d in changed.decisions)
                if (set(after) != set(baseline_ids)
                    or len(after) != len(baseline_ids)
                    or changed.owner_go or changed.verified
                    or changed.execution_allowed
                    or changed.advisory_status != "OPTIONAL_HINTS_ACCEPTED"
                    or any(d.runnable for d in changed.decisions)):
                    raise ValueError("MESA advisory crossed native READY boundary")
            except (ValueError, TypeError):
                # A refused/invalid optional hint must never block native
                # READY evaluation or retain any untrusted experience refs.
                return MESAControllerProposal(
                    plan.digest, plan.blueprint_sha, baseline_ids, (),
                    "MEMORY_REJECTED_FALLBACK",
                )
            baseline_ids = after
            status = "SHADOW_ADVICE_ONLY"
    return MESAControllerProposal(
        plan.digest, plan.blueprint_sha, baseline_ids, tuple(refs), status,
    )
