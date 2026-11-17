"""Read-only app composition for P1. Does not start HTTP server or run tasks."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import re

from my_local_ai.orchestrator import PlanningPreview,preview_plan,redact_preview
from my_local_ai.ui.status_view import StatusSnapshot,load_snapshot


@dataclass(frozen=True)
class AppReadOnlyState:
    implementation: StatusSnapshot
    preview: PlanningPreview

    def to_public_dict(self) -> dict:
        if (self.implementation.operation_allowed or not self.implementation.p2_locked
            or self.preview.can_run_coder or self.preview.can_write_git):
            raise ValueError("P1 app cannot execute")
        return {
            "implementation":self.implementation.to_public_dict(),
            "planning":redact_preview(self.preview),
            "read_only":True,
            "owner_go":False,
            "execution_allowed":False,
        }


def build_read_only_app(
    *, project_root: str | Path, plan_json: str,
    protected_states: dict[str,str],
    independently_verified: Iterable[str] = (),
    active_leases: Iterable[str] = (),
    advisory_json: str | None = None,
    optional_eai_envelope_json: str | None = None,
) -> AppReadOnlyState:
    snapshot=load_snapshot(project_root)
    if snapshot.operation_allowed or not snapshot.p2_locked:
        raise ValueError("non-P1 operation requires separate owner/runtime authorization")
    preview=preview_plan(
        plan_json=plan_json,protected_states=protected_states,
        independently_verified=independently_verified,
        active_leases=active_leases,advisory_json=advisory_json,
        optional_eai_envelope_json=optional_eai_envelope_json,
    )
    return AppReadOnlyState(snapshot,preview)



def safe_code_request_card(preview: object) -> dict:
    """Redacted BE→FE card for source-only worker preparation, no commands."""
    from my_local_ai.orchestrator import ControllerCodePreview
    if not isinstance(preview, ControllerCodePreview):
        raise ValueError("invalid controller code preview")
    if (preview.stage != "CODE_REQUEST_PREPARED_ONLY" or preview.may_execute
        or preview.may_write_git or preview.code_worker_executed
        or preview.owner_signed_go or preview.real_isolation_verified
        or preview.candidate_verified or preview.provider != "LOCAL_QWEN_OPENCODE"
        or preview.advisory_status not in
            {"DISABLED", "OPTIONAL_HINTS_ACCEPTED", "INVALID_HINTS_IGNORED"}
        or type(preview.allowed_file_count) is not int
        or not 1 <= preview.allowed_file_count <= 16
        or not isinstance(preview.task_id,str) or
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}",preview.task_id) is None
        or not isinstance(preview.plan_sha256,str) or
            re.fullmatch(r"[0-9a-f]{64}",preview.plan_sha256) is None
        or not isinstance(preview.baseline_sha,str) or
            re.fullmatch(r"[0-9a-f]{40}",preview.baseline_sha) is None
        or not isinstance(preview.prepared_request_sha256,str) or
            re.fullmatch(r"[0-9a-f]{64}",preview.prepared_request_sha256) is None):
        raise ValueError("unsafe or forged worker preview")
    return {
        "task_id": preview.task_id,
        "provider": preview.provider,
        "allowed_file_count": preview.allowed_file_count,
        "plan_sha256": preview.plan_sha256,
        "baseline_sha": preview.baseline_sha,
        "prepared_request_sha256": preview.prepared_request_sha256,
        "stage": preview.stage,
        "advisor_status": preview.advisory_status,
        "execution_allowed": False,
        "review_status": "F18_HOLD",
        "network_allowed": False,
        "real_device_test": "NOT_RUN",
    }


@dataclass(frozen=True)
class AppReviewHandoff:
    """P1 BE→FE composite card; never gives the browser trusted capabilities."""
    candidate: object

    def to_public_dict(self) -> dict:
        from my_local_ai.orchestrator import ControllerReviewHandoff
        from my_local_ai.review.trusted_runner import redact_isolated_review_intent
        if (not isinstance(self.candidate, ControllerReviewHandoff)
            or self.candidate.stage != "P1_F18_REQUEST_PREPARED_ONLY"
            or self.candidate.model_executed or self.candidate.reviewer_executed
            or self.candidate.trusted_receipt_issued
            or self.candidate.owner_go_verified or self.candidate.may_promote
            or self.candidate.may_publish):
            raise ValueError("unsafe P1 review handoff")
        code = safe_code_request_card(self.candidate.code)
        review = redact_isolated_review_intent(self.candidate.review)
        if (code["task_id"] != review["task_id"]
            or code["plan_sha256"] != review["plan_sha256"]
            or code["baseline_sha"] != review["source_sha"]
            or review["candidate_sha"] == code["baseline_sha"]
            or code["execution_allowed"] is not False
            or review["f18_verified"] is not False):
            raise ValueError("mismatched source and F18 review chain")
        return {
            "worker":code,
            "independent_review":review,
            "stage":"P1_F18_REQUEST_PREPARED_ONLY",
            "read_only":True,
            "execution_allowed":False,
            "owner_go_verified":False,
            "candidate_trusted":False,
            "may_promote":False,
            "may_publish":False,
        }


def build_p1_source_candidate_card(
    project_root: str | Path, *, exact_source_sha: str,
) -> dict:
    """Expose exact-SHA source coverage to the read-only app, not to a runner."""
    from my_local_ai.ui.status_view import evaluate_p1_source_candidate
    return evaluate_p1_source_candidate(
        project_root, exact_source_sha=exact_source_sha,
    ).to_public_dict()


def build_controller_hold_cycle_card(cycle: object) -> dict:
    """Redacted BE->FE result of a real SQLite HOLD, never an execution grant."""
    from my_local_ai.orchestrator import ControllerHoldCycle
    if (not isinstance(cycle, ControllerHoldCycle)
        or cycle.state != "HOLD_F18_INDEPENDENCE_NOT_ESTABLISHED"
        or cycle.task_state_changed is not True
        or type(cycle.event_id) is not int or cycle.event_id <= 0
        or any((
            cycle.coder_executed,cycle.reviewer_executed,
            cycle.trusted_receipt_issued,cycle.lease_created,
            cycle.owner_go_verified,cycle.may_promote,cycle.may_publish,
        ))
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}",cycle.task_id) is None
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}",cycle.run_id) is None
        or any(re.fullmatch(r"[0-9a-f]{64}",value) is None for value in (
            cycle.plan_sha256,cycle.request_sha256,
            cycle.review_policy_sha256,
        ))
        or re.fullmatch(r"[0-9a-f]{40}",cycle.source_sha) is None):
        raise ValueError("untrusted Controller HOLD card")
    return {
        "task_id":cycle.task_id,
        "run_id":cycle.run_id,
        "plan_sha256":cycle.plan_sha256,
        "source_sha":cycle.source_sha,
        "worker_request_sha256":cycle.request_sha256,
        "review_policy_sha256":cycle.review_policy_sha256,
        "event_id":cycle.event_id,
        "state":cycle.state,
        "task_state_changed":True,
        "reviewer_result":"NOT_RUN",
        "owner_go_verified":False,
        "independent_f18_verified":False,
        "execution_allowed":False,
        "may_promote":False,
        "may_publish":False,
        "p2":"LOCKED",
    }
