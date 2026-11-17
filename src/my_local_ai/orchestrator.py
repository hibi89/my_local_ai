"""My Local AI native Controller orchestration, P1 non-executing integration.

Synthetic/owner-protected inputs are treated as DATA. The Controller proposes
work only, while task execution, signer, OS-isolated runner, F18, Git CAS,
remote publication and real-use approval remain separate disabled ports.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
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
    if (not isinstance(preview, PlanningPreview)
        or preview.phase != "P1_IMPLEMENTATION"
        or preview.owner_go_verified or preview.f18_independently_verified
        or preview.can_run_coder or preview.can_write_git or preview.can_publish_remote
        or preview.p2_locked is not True
        or type(preview.task_count) is not int or not 1 <= preview.task_count <= 256
        or not isinstance(preview.plan_sha256, str) or
            re.fullmatch(r"[0-9a-f]{64}", preview.plan_sha256) is None
        or not isinstance(preview.source_sha, str) or
            re.fullmatch(r"[0-9a-f]{40}", preview.source_sha) is None
        or preview.advisory_status not in
            {"DISABLED", "OPTIONAL_HINTS_ACCEPTED", "INVALID_HINTS_IGNORED"}
        or not isinstance(preview.candidate_task_ids, tuple)
        or len(preview.candidate_task_ids) > preview.task_count
        or len(set(preview.candidate_task_ids)) != len(preview.candidate_task_ids)
        or any(not isinstance(x,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}",x)
               for x in preview.candidate_task_ids)):
        raise ValueError("invalid or unsafe preview")
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


# Non-executing controller -> local OpenCode code-request composition.
# It deliberately never calls run_in_sandbox, invokes a model or verifies F18.
from dataclasses import replace as _replace
from hashlib import sha256 as _sha256
from pathlib import Path as _Path
from my_local_ai.ax_runtime.opencode_worker import prepare_opencode_run, WorkerHold


@dataclass(frozen=True)
class ControllerCodePreview:
    task_id: str
    plan_sha256: str
    baseline_sha: str
    provider: str
    allowed_file_count: int
    prepared_request_sha256: str
    stage: str = "CODE_REQUEST_PREPARED_ONLY"
    owner_signed_go: bool = False
    real_isolation_verified: bool = False
    candidate_verified: bool = False
    code_worker_executed: bool = False
    may_execute: bool = False
    may_write_git: bool = False


def preview_local_code_request(
    *, plan_json: str, protected_states: dict[str, str], task_id: str,
    disposable_worktree: str | _Path, original_checkout: str | _Path,
    active_leases: Iterable[str] = (), advisory_json: str | None = None,
) -> ControllerCodePreview:
    """Validate a Controller-ready task, then prepare a local-only request.

    Code candidate is a *shape* only and deliberately not handed to a
    process. Never pass original goal/prompt, customer content, or secrets
    into the simulated worker. Actual protected owner signer, OS sandbox
    and independent reviewer must later authorize a real invocation.
    """
    if not isinstance(task_id, str):
        raise ValueError("task ID must be a string")
    plan = PlanSpec.parse_json(plan_json)
    proposed = Controller(plan).propose(
        protected_states, independently_verified=(),
        active_leases=active_leases, advisory_json=advisory_json,
    )
    if (proposed.execution_allowed or proposed.owner_go or proposed.verified
        or task_id not in {item.task_id for item in proposed.decisions}):
        raise ValueError("task not eligible as safe Controller code candidate")
    task = next(item for item in plan.tasks if item.task_id == task_id)
    # A transient locally recomputed plan digest is used for format
    # validation only. This does NOT approve the underlying PlanSpec.
    pinned_task = _replace(task, plan_sha=plan.digest)
    prompt = "SYNTHETIC NONEXECUTING REQUEST FOR " + task.task_id
    prepared = prepare_opencode_run(
        pinned_task, plan_sha256=plan.digest, source_sha=task.source_sha,
        disposable_worktree=str(disposable_worktree),
        original_checkout=str(original_checkout),
        prompt=prompt,
    )
    if (prepared.untrusted is not True or prepared.task_id != task_id
        or prepared.source_sha != plan.blueprint_sha
        or prepared.plan_sha256 != plan.digest
        or not set(prepared.allowed_paths).issubset(task.allowed_paths)):
        raise ValueError("prepared worker request mismatch")
    # Hash the request schema locally. No command, source, prompt or
    # environment values are published into the status interface.
    identity = (prepared.task_id + "|" + prepared.plan_sha256
                + "|" + prepared.source_sha + "|"
                + ",".join(prepared.allowed_paths)).encode("ascii")
    return ControllerCodePreview(
        task_id, plan.digest, task.source_sha, "LOCAL_QWEN_OPENCODE",
        len(prepared.allowed_paths), _sha256(identity).hexdigest(),
    )
