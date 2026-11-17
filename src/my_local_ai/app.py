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
) -> AppReadOnlyState:
    snapshot=load_snapshot(project_root)
    if snapshot.operation_allowed or not snapshot.p2_locked:
        raise ValueError("non-P1 operation requires separate owner/runtime authorization")
    preview=preview_plan(
        plan_json=plan_json,protected_states=protected_states,
        independently_verified=independently_verified,
        active_leases=active_leases,advisory_json=advisory_json,
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
        "execution_allowed": False,
        "review_status": "F18_HOLD",
        "network_allowed": False,
        "real_device_test": "NOT_RUN",
    }
