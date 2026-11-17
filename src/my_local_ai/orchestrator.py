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

# V1.3: static risk decision, not the real OS/code execution path.
# Keep the public call explicitly nonexecuting. Actual dispatch must also
# enforce the protected F18/owner/typed-operator safety gate in later SWUs.
from my_local_ai.security.codeshield_contracts import (
    CodeShieldContext as _CodeShieldContext,
    ScannerEvidence as _ScannerEvidence,
    ActionKind as _ActionKind,
)
from my_local_ai.controller.codeshield import (
    evaluate_codeshield_candidate as _evaluate_codeshield_candidate,
    read_only_decision_status as _read_only_decision_status,
)


def preview_codeshield_static(
    *, context: _CodeShieldContext,
    candidate_python_sources: dict[str, bytes | str],
    scanner_evidence: tuple[_ScannerEvidence, ...] = (),
    action: _ActionKind = _ActionKind.STATIC_READ,
) -> dict[str, object]:
    """Controller-facing read-only static code preflight; never runs code.

    Returned fields are redacted and cannot issue F18 receipts, grant owner
    scope, modify Git, or launch a checker/executable themselves.
    """
    reviewed = _evaluate_codeshield_candidate(
        context, candidate_python_sources=candidate_python_sources,
        scanner_evidence=scanner_evidence, action=action,
    )
    result = _read_only_decision_status(reviewed)
    if (result["execution_allowed"] is not False
        or result["owner_go_verified"] is not False
        or result["f18_verified"] is not False
        or result["can_write_git"] is not False
        or result["can_publish_remote"] is not False):
        raise ValueError("unsafe CodeShield preview")
    return result

# Bounded source-on-disk → static scanner adapter → redacted result.
# Never convert these results to CodeRunner, F18 TrustedReceipt or Git CAS.
from my_local_ai.controller.codeshield import audit_scoped_sources as _audit_scoped_sources
from my_local_ai.security.supply_chain import OfflineDatabasePin as _OfflineDatabasePin


def preview_codeshield_scoped_static(
    *, context: _CodeShieldContext, worktree: str | _Path,
    original_checkout: str | _Path, changed_python_paths: tuple[str, ...],
    ruff_binary: str | _Path | None = None,
    gitleaks_binary: str | _Path | None = None,
    semgrep_binary: str | _Path | None = None,
    local_semgrep_rules: str | _Path | None = None,
    local_osv_cache: str | _Path | None = None,
    offline_database_pin: _OfflineDatabasePin | None = None,
) -> dict[str, object]:
    """Owner-callable read-only static audit. No owner/F18 execution unlock.

    Results are NOT verified source provenance, Git diff, OS policy
    attestation or independent scanner execution proof. Unknown => HOLD.
    """
    audit = _audit_scoped_sources(
        context, worktree=worktree, original_checkout=original_checkout,
        changed_python_paths=changed_python_paths,
        ruff_binary=ruff_binary, gitleaks_binary=gitleaks_binary,
        semgrep_binary=semgrep_binary, local_semgrep_rules=local_semgrep_rules,
        local_osv_cache=local_osv_cache,
        offline_database_pin=offline_database_pin,
    )
    result = audit.to_redacted_dict()
    if (result.get("execution_allowed") is not False
        or result.get("owner_go_verified") is not False
        or result.get("independent_f18_verified") is not False
        or result.get("git_promotion_allowed") is not False):
        raise ValueError("untrusted CodeShield static audit result")
    return result


# No runtime dispatcher is exported in P1. A caller attempting to advance
# a static CodeShield result into owner/F18/OS/Git authority receives HOLD.
from my_local_ai.controller.codeshield import (
    LocalStaticAudit as _LocalStaticAudit,
    preview_protected_dispatch_hold as _preview_protected_dispatch_hold,
)


def preview_codeshield_controller_dispatch_hold(
    *, context: _CodeShieldContext,
    audit: _LocalStaticAudit | None = None,
    action: _ActionKind = _ActionKind.UNTRUSTED_EXECUTION,
) -> dict[str, object]:
    """Controller -> phase-ordered denial: never spawn, sign, merge or publish.

    The returned dictionary contains no privileged grant. Neither owner
    consent references nor model-reported scanner PASS are trusted evidence.
    """
    decision = _preview_protected_dispatch_hold(
        context, audit=audit, action=action,
    )
    payload = decision.to_redacted_dict()
    if (payload["stage"] != "P1_CONTROLLER_DISPATCH_DENIED"
        or payload["owner_consent_verified"] is not False
        or payload["isolated_runtime_attested"] is not False
        or payload["f18_independently_verified"] is not False
        or payload["git_cas_verified"] is not False
        or payload["execution_allowed"] is not False
        or payload["can_modify_original"] is not False
        or payload["can_promote_git"] is not False
        or payload["can_publish_remote"] is not False):
        raise ValueError("unsafe CodeShield controller dispatch state")
    return payload


def inspect_codeshield_controller_action_scoped(
    *, plan_json: str, context: _CodeShieldContext,
    protected_states: dict[str, str],
    worktree: str | _Path, original_checkout: str | _Path,
    changed_python_paths: tuple[str, ...],
    action: _ActionKind = _ActionKind.UNTRUSTED_EXECUTION,
    active_leases: tuple[str, ...] = (),
    ruff_binary: str | _Path | None = None,
    gitleaks_binary: str | _Path | None = None,
    semgrep_binary: str | _Path | None = None,
    local_semgrep_rules: str | _Path | None = None,
    local_osv_cache: str | _Path | None = None,
    offline_database_pin: _OfflineDatabasePin | None = None,
) -> dict[str, object]:
    """Actual P1 request -> immutable Controller -> static scan -> deny.

    Fail closed on stale task/plan/source/allowed paths BEFORE reading files or
    consulting optional pinned scanners. Pinned scanner execution never
    authorizes untrusted candidate execution, owner action, F18, or Git.
    """
    from my_local_ai.contracts.plan import PlanSpec
    from my_local_ai.controller.codeshield import (
        deny_codeshield_controller_plan_action,
    )

    if not isinstance(plan_json, str):
        raise ValueError("untrusted CodeShield plan")
    plan = PlanSpec.parse_json(plan_json)
    # First check task/source/lease/allowed-path shape. This is intentionally
    # a denial, and is never treated as an owner-approved authorization.
    initial = deny_codeshield_controller_plan_action(
        plan, context, states=protected_states, audit=None,
        action=action, active_leases=active_leases,
    )
    if (initial.may_launch_untrusted is not False
        or initial.may_promote_git is not False
        or initial.owner_consent_verified is not False):
        raise ValueError("untrusted Controller state")
    audited = _audit_scoped_sources(
        context, worktree=worktree, original_checkout=original_checkout,
        changed_python_paths=changed_python_paths,
        ruff_binary=ruff_binary, gitleaks_binary=gitleaks_binary,
        semgrep_binary=semgrep_binary, local_semgrep_rules=local_semgrep_rules,
        local_osv_cache=local_osv_cache,
        offline_database_pin=offline_database_pin,
    )
    final = deny_codeshield_controller_plan_action(
        plan, context, states=protected_states, audit=audited,
        action=action, active_leases=active_leases,
    ).to_redacted_dict()
    if (final["stage"] != "P1_CONTROLLER_DISPATCH_DENIED"
        or any(final[flag] is not False for flag in (
            "owner_consent_verified", "isolated_runtime_attested",
            "f18_independently_verified", "git_cas_verified",
            "execution_allowed", "can_modify_original",
            "can_promote_git", "can_publish_remote",
        ))):
        raise ValueError("untrusted Controller dispatch")
    return {
        "static_audit": audited.to_redacted_dict(),
        "controller_dispatch": final,
        "protected_os_broker": "HOLD",
        "independent_f18": "HOLD",
        "owner_grant": "HOLD",
        "phase": "P1_SOURCE_ONLY",
        "execution_allowed": False,
        "owner_go_verified": False,
        "p2": "LOCKED",
    }



# MLA-SWU-038: EAI-style Pure Player contract adapted to MLA's own Controller.
# This registry deliberately offers ONLY trusted, in-process bounded CPU
# preflight operations; it never dispatches model-written Python/JS/commands.
_PURE_PLAYER_TYPED_OPERATIONS = frozenset({
    "PLAN_SCOPE_REVIEW", "STATIC_AST_REVIEW",
})


def inspect_pure_player_nonexecuting_cycle(
    *, plan_json: str, context: _CodeShieldContext,
    protected_states: dict[str, str], operator_id: str,
    candidate_python_sources: dict[str, bytes | str] | None = None,
    active_leases: tuple[str, ...] = (),
) -> dict[str, object]:
    """App -> immutable Controller -> fixed pure op -> safety HOLD result.

    The caller supplies task/plan data, NOT an executable callback or argv.
    No generated code/guest test/shell/OS/container/network action can run.
    A valid static result is evidence about candidate text, not F18 or GO.
    """
    from my_local_ai.contracts.plan import PlanSpec
    from my_local_ai.controller.codeshield import (
        deny_codeshield_controller_plan_action,
    )
    if (type(operator_id) is not str
        or operator_id not in _PURE_PLAYER_TYPED_OPERATIONS
        or type(plan_json) is not str
        or not isinstance(context, _CodeShieldContext)
        or type(active_leases) is not tuple):
        raise ValueError("unsupported Pure Player typed operator")
    if (operator_id == "PLAN_SCOPE_REVIEW"
        and candidate_python_sources is not None):
        raise ValueError("plan-only operation cannot consume generated source")
    if (operator_id == "STATIC_AST_REVIEW"
        and (type(candidate_python_sources) is not dict
             or not candidate_python_sources)):
        raise ValueError("bounded candidate source required")
    plan = PlanSpec.parse_json(plan_json)
    # Check exact task/source/path/lease shape BEFORE any static source parse.
    denial = deny_codeshield_controller_plan_action(
        plan, context, states=protected_states,
        audit=None, action=_ActionKind.STATIC_READ,
        active_leases=active_leases,
    ).to_redacted_dict()
    if (denial["stage"] != "P1_CONTROLLER_DISPATCH_DENIED"
        or denial["execution_allowed"] is not False
        or denial["owner_consent_verified"] is not False
        or denial["f18_independently_verified"] is not False
        or denial["can_promote_git"] is not False):
        raise ValueError("Pure Player Controller authority mismatch")
    # Actual MLA-SWU-015/031 fixed CPU operator, after Controller scope check.
    from my_local_ai.ax_runtime.isolation_runner import (
        prepare_pure_player_candidate, run_pure_player_nonexecuting_candidate,
        deny_pure_player_network_operation,
    )
    deny_pure_player_network_operation(operator_id)
    pure_candidate = prepare_pure_player_candidate(
        context, operator_id=operator_id,
        proposed_files=(candidate_python_sources
                        if operator_id == "STATIC_AST_REVIEW" else None),
    )
    pure_result = run_pure_player_nonexecuting_candidate(
        context, pure_candidate,
    )
    if (pure_result["generated_code_executed"] is not False
        or pure_result["network_egress_allowed"] is not False
        or pure_result["host_network_isolation_attested"] is not False
        or pure_result["git_promotion_allowed"] is not False):
        raise ValueError("invalid fixed Pure Player evaluation")
    static = None
    if operator_id == "STATIC_AST_REVIEW":
        static = preview_codeshield_static(
            context=context,
            candidate_python_sources=candidate_python_sources,
            action=_ActionKind.STATIC_READ,
        )
        if (static["execution_allowed"] is not False
            or static["owner_go_verified"] is not False
            or static["f18_verified"] is not False):
            raise ValueError("untrusted Pure Player static result")
    return {
        "stage": "PURE_PLAYER_NONEXECUTING_HOLD",
        "operator_id": operator_id,
        "context_sha256": context.fingerprint_sha256,
        "candidate_git_sha": context.candidate_git_sha,
        "controller_dispatch": denial,
        "static_review": static,
        "pure_candidate": pure_result,
        "typed_operator_executed": True,
        "model_code_executed": False,
        "owner_go_verified": False,
        "independent_f18_verified": False,
        "execution_allowed": False,
        "git_promotion_allowed": False,
        "network_egress_allowed": False,
        "p2": "LOCKED",
    }



def generate_public_pure_player_candidate(
    *, plan_json: str, context: _CodeShieldContext,
    protected_states: dict[str, str], coding_request: str,
    model_lock, budget, active_leases: tuple[str, ...] = (),
) -> dict[str, object]:
    """Native Controller -> single host Qwen -> bounded text -> Pure Player.

    Only explicit PUBLIC_SYNTHETIC_ONLY prompts may reach 127.0.0.1 Ollama.
    Generated code/tests are never executed, imported, promoted or applied.
    A real owner key, F18 proof and OS egress attestation are NEVER inferred.
    """
    from my_local_ai.contracts.plan import PlanSpec
    from my_local_ai.controller.codeshield import (
        deny_codeshield_controller_plan_action,
    )
    from my_local_ai.ax_runtime.worker_lock import (
        OneModelLock, ModelLockBusy, ModelLockUnsafe,
    )
    from my_local_ai.ax_runtime.budgets import BudgetGuard
    from my_local_ai.ax_runtime.isolation_runner import (
        HostQwenGenerationRequest, UntrustedHostQwenFiles,
        prepare_host_qwen_generation, infer_host_qwen_public_synthetic,
        prepare_pure_player_candidate,
    )
    from my_local_ai.security.codeshield_contracts import (
        CodeShieldHold, DataClass,
    )
    if (type(plan_json) is not str
        or not isinstance(context, _CodeShieldContext)
        or context.data_class != DataClass.PUBLIC_SYNTHETIC
        or type(coding_request) is not str
        or type(active_leases) is not tuple
        or not isinstance(model_lock, OneModelLock)
        or not isinstance(budget, BudgetGuard)):
        raise ValueError("unsafe local Pure Player generation request")
    plan = PlanSpec.parse_json(plan_json)
    denial = deny_codeshield_controller_plan_action(
        plan, context, states=protected_states, audit=None,
        action=_ActionKind.STATIC_READ, active_leases=active_leases,
    )
    if (denial.owner_consent_verified or denial.f18_independently_verified
        or denial.may_launch_untrusted or denial.may_promote_git):
        raise ValueError("unexpected Controller authority")
    req = prepare_host_qwen_generation(
        context, run_id=context.run_id, coding_request=coding_request,
    )
    try:
        with model_lock:
            proposed = infer_host_qwen_public_synthetic(
                req, context, budget=budget,
            )
    except (ModelLockBusy, ModelLockUnsafe):
        raise ValueError("local model lock unavailable") from None
    if (not isinstance(proposed, UntrustedHostQwenFiles)
        or proposed.state != "UNTRUSTED_HOST_MODEL_OUTPUT_F18_REQUIRED"
        or proposed.request_sha256 != req.request_sha256
        or proposed.task_id != context.task_id
        or proposed.run_id != context.run_id
        or proposed.plan_sha256 != context.plan_sha256
        or proposed.source_sha != context.source_git_sha
        or proposed.files_applied_to_original
        or proposed.generated_code_executed
        or proposed.independent_f18_verified
        or proposed.can_publish):
        raise ValueError("untrusted generated source envelope")
    # Re-check case folding, allowed_paths, sizes, type and content digest.
    import json as _json
    from hashlib import sha256 as _sha
    canonical = _json.dumps(
        proposed.files, sort_keys=True, separators=(",",":"),
        ensure_ascii=True,
    ).encode("utf-8")
    if proposed.files_sha256 != _sha(
        b"mla-untrusted-host-files/v1|" + canonical,
    ).hexdigest():
        raise ValueError("changed generated file inventory")
    pure = prepare_pure_player_candidate(
        context, operator_id="STATIC_AST_REVIEW",
        proposed_files=dict(proposed.files),
    )
    if len(pure.files) != len(proposed.files):
        raise ValueError("duplicate or altered generated file paths")
    result = inspect_pure_player_nonexecuting_cycle(
        plan_json=plan_json, context=context,
        protected_states=protected_states, operator_id="STATIC_AST_REVIEW",
        candidate_python_sources=dict(pure.files),
        active_leases=active_leases,
    )
    if (result["execution_allowed"] is not False
        or result["independent_f18_verified"] is not False
        or result["git_promotion_allowed"] is not False
        or result["pure_candidate"]["network_egress_allowed"] is not False):
        raise ValueError("Pure Player must never promote model output")
    return {
        "stage":"PUBLIC_SYNTHETIC_QWEN_NONEXECUTING_HOLD",
        "source_git_sha":context.source_git_sha,
        "candidate_git_sha":context.candidate_git_sha,
        "prompt_sha256":req.prompt_sha256,
        "request_sha256":req.request_sha256,
        "files_sha256":proposed.files_sha256,
        "file_count":len(proposed.files),
        "pure_player":result,
        "generated_code_executed":False,
        "owner_go_verified":False,
        "independent_f18_verified":False,
        "git_promotion_allowed":False,
        "host_no_egress_attested":False,
        "p2":"LOCKED",
    }
