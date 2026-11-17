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
    optional_eai_envelope_json: str | None = None,
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
        optional_eai_envelope_json=optional_eai_envelope_json,
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
    advisory_status: str = "DISABLED"


def preview_local_code_request(
    *, plan_json: str, protected_states: dict[str, str], task_id: str,
    disposable_worktree: str | _Path, original_checkout: str | _Path,
    active_leases: Iterable[str] = (), advisory_json: str | None = None,
    optional_eai_envelope_json: str | None = None,
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
        optional_eai_envelope_json=optional_eai_envelope_json,
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
        advisory_status=proposed.advisory_status,
    )


# Pure Controller -> prepared local coder -> independent F18 *HOLD* contract.
# A caller's candidate SHA is merely a proposed value, never a reviewed Git ref.
from my_local_ai.review.trusted_runner import (
    IsolatedReviewerIntent, build_reviewer_policy, prepare_review_request,
    plan_isolated_reviewer,
)


@dataclass(frozen=True)
class ControllerReviewHandoff:
    code: ControllerCodePreview
    review: IsolatedReviewerIntent
    stage: str = "P1_F18_REQUEST_PREPARED_ONLY"
    model_executed: bool = False
    reviewer_executed: bool = False
    trusted_receipt_issued: bool = False
    owner_go_verified: bool = False
    may_promote: bool = False
    may_publish: bool = False


def preview_f18_review_handoff(
    *, plan_json: str, protected_states: dict[str, str], task_id: str,
    disposable_worktree: str | _Path, original_checkout: str | _Path,
    candidate_sha: str, run_id: str, lease_epoch: int,
    reviewer_binary_sha256_claim: str,
    active_leases: Iterable[str] = (),
    advisory_json: str | None = None,
    optional_eai_envelope_json: str | None = None,
) -> ControllerReviewHandoff:
    """Compose typed data-only worker and independent reviewer requests.

    This performs no model call, Git readback, guest process launch, signing,
    owner approval, OS verification or trusted receipt creation. A fake
    candidate SHA is never accepted as an attested diff.
    """
    code = preview_local_code_request(
        plan_json=plan_json,protected_states=protected_states,
        task_id=task_id,disposable_worktree=disposable_worktree,
        original_checkout=original_checkout,active_leases=active_leases,
        advisory_json=advisory_json,
        optional_eai_envelope_json=optional_eai_envelope_json,
    )
    if (code.owner_signed_go or code.real_isolation_verified
        or code.candidate_verified or code.code_worker_executed
        or code.may_execute or code.may_write_git):
        raise ValueError("untrusted Controller-to-F18 handoff")
    policy = build_reviewer_policy()
    required = tuple(item.check_id for item in policy.checks)
    request = prepare_review_request(
        task_id=code.task_id,run_id=run_id,candidate_sha=candidate_sha,
        source_sha=code.baseline_sha,plan_sha256=code.plan_sha256,
        lease_epoch=lease_epoch,trusted_required_argv_ids=required,
    )
    review = plan_isolated_reviewer(
        request,policy,
        protected_reviewer_binary_sha256=reviewer_binary_sha256_claim,
        trusted_source_sha=code.baseline_sha,
        trusted_plan_sha256=code.plan_sha256,
        trusted_candidate_sha=candidate_sha,
    )
    if (review.executable or review.can_issue_trusted_receipt or review.host_fallback
        or review.task_id != code.task_id
        or review.source_sha != code.baseline_sha
        or review.plan_sha256 != code.plan_sha256):
        raise ValueError("untrusted F18 handoff output")
    return ControllerReviewHandoff(code,review)


# SWU-038: a real owner-local DB state transition for a single blocked
# controller -> code request -> independent reviewer *request*. The worker
# and reviewer are not run while F18/OS signer remains unavailable.
@dataclass(frozen=True)
class ControllerHoldCycle:
    task_id: str
    run_id: str
    plan_sha256: str
    source_sha: str
    request_sha256: str
    review_policy_sha256: str
    event_id: int
    state: str = "HOLD_F18_INDEPENDENCE_NOT_ESTABLISHED"
    task_state_changed: bool = True
    coder_executed: bool = False
    reviewer_executed: bool = False
    trusted_receipt_issued: bool = False
    lease_created: bool = False
    owner_go_verified: bool = False
    may_promote: bool = False
    may_publish: bool = False


def persist_controller_review_hold_cycle(
    owned_db, *, plan_json: str, task_id: str,
    disposable_worktree: str | _Path, original_checkout: str | _Path,
    run_id: str, candidate_sha: str, reviewer_binary_sha256_claim: str,
    lease_epoch: int = 1,
) -> ControllerHoldCycle:
    """Pin native Controller and F18 *request* before atomically holding task.

    The candidate SHA is untrusted input, not a coder run result. A real
    reviewed candidate needs a separate OS-isolated runner, live lease,
    independent signer and reviewer; none is inferred or created here.
    """
    from my_local_ai.state.sqlite_store import _write_owned_transaction

    plan = PlanSpec.parse_json(plan_json)
    if (not isinstance(task_id, str) or
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", task_id) is None
        or task_id not in {task.task_id for task in plan.tasks}
        or not isinstance(run_id, str) or
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", run_id) is None):
        raise ValueError("invalid Controller cycle identity")

    def transition(db):
        record = db.execute(
            "SELECT plan_sha,blueprint_sha,state FROM plans WHERE plan_id=?",
            (plan.plan_id,),
        ).fetchone()
        if (record is None or record[:2] != (plan.digest, plan.blueprint_sha)
            or record[2] not in ("AWAITING_OWNER", "APPROVED")):
            raise ValueError("stale or unavailable owner plan")
        rows = db.execute(
            "SELECT task_id,source_sha,state FROM tasks WHERE plan_id=?",
            (plan.plan_id,),
        ).fetchall()
        if len(rows) != len(plan.tasks):
            raise ValueError("incomplete task ledger")
        known = {item.task_id for item in plan.tasks}
        states = {}
        for tid, source, state in rows:
            if (tid not in known or tid in states or source != plan.blueprint_sha):
                raise ValueError("task/source mismatch")
            states[tid] = state
        if states.get(task_id) != "READY":
            raise ValueError("task is not READY")
        active = db.execute(
            "SELECT task_id FROM leases WHERE plan_id=?",
            (plan.plan_id,),
        ).fetchall()
        if any(row[0] not in known for row in active):
            raise ValueError("untrusted active lease")
        active_ids = tuple(row[0] for row in active)
        if task_id in active_ids:
            raise ValueError("task has active lease")
        if db.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
            raise ValueError("run ID must not be reused")

        prepared = preview_f18_review_handoff(
            plan_json=plan_json, protected_states=states, task_id=task_id,
            disposable_worktree=disposable_worktree,
            original_checkout=original_checkout,
            candidate_sha=candidate_sha, run_id=run_id,
            lease_epoch=lease_epoch,
            reviewer_binary_sha256_claim=reviewer_binary_sha256_claim,
            active_leases=active_ids,
        )
        if (prepared.model_executed or prepared.reviewer_executed
            or prepared.trusted_receipt_issued or prepared.owner_go_verified
            or prepared.may_promote or prepared.may_publish
            or prepared.code.may_execute or prepared.review.executable
            or prepared.review.can_issue_trusted_receipt):
            raise ValueError("untrusted F18 privilege")
        if (prepared.code.plan_sha256 != plan.digest
            or prepared.code.baseline_sha != plan.blueprint_sha
            or prepared.review.run_id != run_id
            or prepared.review.lease_epoch != lease_epoch
            or prepared.review.candidate_sha != candidate_sha):
            raise ValueError("controller/reviewer chain mismatch")
        changed = db.execute(
            "UPDATE tasks SET state='HOLD' WHERE plan_id=? AND task_id=? "
            "AND source_sha=? AND state='READY'",
            (plan.plan_id, task_id, plan.blueprint_sha),
        )
        if changed.rowcount != 1:
            raise ValueError("concurrent Controller state change")
        # Do not store raw model output, code, filesystem paths or secrets.
        safe_summary = _sha256(
            ("mla-cycle-hold/v1|" + plan.digest + "|" + task_id +
             "|" + run_id + "|" + str(lease_epoch) + "|" +
             prepared.review.policy_sha256).encode("ascii")
        ).hexdigest()
        event = db.execute(
            "INSERT INTO events(plan_id,event_kind,safe_summary) "
            "VALUES(?,'CONTROLLER_REVIEW_HELD',?)",
            (plan.plan_id, safe_summary),
        )
        return ControllerHoldCycle(
            task_id, run_id, plan.digest, plan.blueprint_sha,
            prepared.code.prepared_request_sha256,
            prepared.review.policy_sha256, event.lastrowid,
        )

    return _write_owned_transaction(owned_db, transition)
