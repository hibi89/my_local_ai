"""My Local AI native Controller orchestration, P1 non-executing integration.

Synthetic/owner-protected inputs are treated as DATA. The Controller proposes
work only, while task execution, signer, OS-isolated runner, F18, Git CAS,
remote publication and real-use approval remain separate disabled ports.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from my_local_ai.contracts.plan import PlanSpec
from my_local_ai.controller.decision import Controller


@dataclass(frozen=True)
class PlanningPreview:
    plan_sha256: str
    source_sha: str
    task_count: int
    candidate_task_ids: tuple[str, ...]
    advisory_status: str
    phase: str = "P1_IMPLEMENTATION"
    owner_go_verified: bool = False
    f18_independently_verified: bool = False
    can_run_coder: bool = False
    can_write_git: bool = False
    can_publish_remote: bool = False
    p2_locked: bool = True


def preview_plan(
    *, plan_json: str,
    protected_states: dict[str,str],
    independently_verified: Iterable[str] = (),
    active_leases: Iterable[str] = (),
    advisory_json: str | None = None,
) -> PlanningPreview:
    """No file writes, shell commands, HTTP, model, EAI engine, or owner GO.

    This P1 preview accepts caller-provided state for a *what-if* summary.
    A caller's independently_verified list is NOT trusted F18 evidence;
    candidates are never returned as executable work.
    """
    parsed=PlanSpec.parse_json(plan_json)
    result=Controller(parsed).propose(
        protected_states,independently_verified=independently_verified,
        active_leases=active_leases,advisory_json=advisory_json,
    )
    if result.execution_allowed or result.owner_go or result.verified:
        raise ValueError("untrusted planner privilege")
    if any(c.runnable or c.plan_sha256 != parsed.digest for c in result.decisions):
        raise ValueError("untrusted candidate")
    return PlanningPreview(
        parsed.digest,parsed.blueprint_sha,len(parsed.tasks),
        tuple(c.task_id for c in result.decisions),result.advisory_status,
    )


def redact_preview(preview: PlanningPreview) -> dict:
    """Only safe identifiers; never serialize plan goals/paths/prompts/data."""
    if not isinstance(preview,PlanningPreview) or preview.can_run_coder:
        raise ValueError("invalid preview")
    return {
        "phase":preview.phase,
        "source_sha":preview.source_sha,
        "plan_sha256":preview.plan_sha256,
        "task_count":preview.task_count,
        "candidate_task_ids":list(preview.candidate_task_ids),
        "advisory_status":preview.advisory_status,
        "execution_allowed":False,
        "owner_go_verified":False,
        "f18_independently_verified":False,
        "can_write_git":False,
        "can_publish_remote":False,
        "p2_locked":True,
    }
