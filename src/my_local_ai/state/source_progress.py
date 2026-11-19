"""Validated source candidate counts for the CLI and read-only dashboard."""
from __future__ import annotations

from pathlib import Path
import stat

from ..contracts.task import safe_path
from .local_files import local_path_stat, read_local_metadata


def _source_file_exists(root: Path, name: str) -> bool:
    try:
        relative = safe_path(name)
        if not relative.startswith("src/my_local_ai/"):
            return False
        return stat.S_ISREG(local_path_stat(root / relative).st_mode)
    except (OSError, ValueError, TypeError):
        return False


def load_v13_swu_progress(root: Path) -> dict:
    """P1 code inventory by FINAL_BLUEPRINT J/K/L, never an approval gate.

    The initial feature snapshot was 13 CodeShield candidates. New P1 code
    added on active dev is counted only when its queue entry and exact source
    inventory agree; this local count never grants OS/F18/runtime authority.
    """
    record = read_local_metadata(root / "P1_V1_3_SWU_REBASELINE.json")
    queue = read_local_metadata(root / "P1_SWU_TASK_QUEUE.json")
    if (not isinstance(record, dict)
        or record.get("schema") != "mla-v1.3-swu-scope/v1"
        or record.get("project") != "hibi89/my_local_ai"
        or record.get("active_dev_branch") != "dev/instant-implementation-v1"
        or record.get("code_shield_feature_branch") != "feature/code-shield-lightweight-v1"
        or record.get("phase") != "P1_IMPLEMENTATION"
        or record.get("p2_status") != "LOCKED"
        or record.get("p2_verified_rate") != "UNASSESSED"
        or record.get("owner_go") is not False
        or record.get("integration_gate") !=
            "SOURCE_MERGED_P1_UNVERIFIED"
        or record.get("required_v13_swu_total") != 55
        or record.get("legacy_swu_total") != 39
        or record.get("code_shield_swu_total") != 16
        or not isinstance(queue, dict)
        or queue.get("swu_count") != 39
        or queue.get("req_count") != 30
        or queue.get("p2") != "LOCKED"
        or queue.get("owner_go") is not False
        or queue.get("first_ready") != []
        or not isinstance(queue.get("tasks"), list)
        or len(queue["tasks"]) != 39):
        raise ValueError("untrusted P1 V1.3 SWU rebaseline")
    ids = set()
    active_count = 0
    for item in queue["tasks"]:
        if (not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or item["id"] in ids
            or item.get("code_status") not in (
                "SOURCE_COMPLETE_P2_PENDING", "BLOCKED_TRUST",
                "REBASELINE_REWORK_REQUIRED"
            )):
            raise ValueError("inconsistent MLA SWU status")
        ids.add(item["id"])
        active_count += (item["code_status"] == "SOURCE_COMPLETE_P2_PENDING")
    if (active_count != queue.get("source_complete_swu_count")
        or active_count > 39 or len(ids) != 39):
        raise ValueError("stale MLA SWU progress")
    extension = record.get("code_shield_swu_inventory")
    if not isinstance(extension, list) or len(extension) != 16:
        raise ValueError("incomplete CodeShield inventory")
    staged = 0
    integrated = 0
    ext_ids = set()
    for item in extension:
        if (not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or item["id"] in ext_ids or item["id"] in ids
            or type(item.get("integrated_into_dev")) is not bool
            or item.get("integrated_into_dev") is not
                 (item.get("code_status") == "SOURCE_CONNECTED_IMPLEMENTED_UNVERIFIED")
            or type(item.get("source_candidate_on_feature")) is not bool
            or (item.get("source_candidate_on_feature")
                and item.get("integrated_into_dev") is not True)):
            raise ValueError("untrusted CodeShield integration evidence")
        ext_ids.add(item["id"])
        staged += item["source_candidate_on_feature"]
        integrated += item["integrated_into_dev"]
    zero_vm = record.get("zero_vm_rebaseline")
    if (not isinstance(zero_vm, dict)
        or zero_vm.get("design_sha") != "05f51849c0efe7303bf57cb78dff576e441063f5"
        or zero_vm.get("current", {}).get("mla") != active_count
        or zero_vm.get("current", {}).get("code_shield") != integrated
        or zero_vm.get("current", {}).get("completed") != active_count + integrated
        or zero_vm.get("current", {}).get("total") != 55
        or zero_vm.get("runtime_go") is not False
        or zero_vm.get("p2") != "LOCKED"):
        raise ValueError("stale zero-VM SWU rebaseline")
    if (ext_ids != {"CS-SWU-" + str(i).zfill(3) for i in range(1, 17)}
        or staged != record.get("code_shield_source_candidate_unmerged_at_rebaseline")
        or integrated != record.get("code_shield_source_candidates_integrated")
        or integrated < staged or integrated > 16):
        raise ValueError("invalid CodeShield SWU crosswalk")
    # The source queue is the public P1 audit inventory, not a permission grant.
    shield = read_local_metadata(root / "docs" / "OPTIONAL_CODESHIELD_TASK_QUEUE.json")
    swus = shield.get("p1_source_swu_tasks")
    if (shield.get("project") != "hibi89/my_local_ai"
        or shield.get("p1_source_swu_total") != 16
        or shield.get("p1_source_swu_implemented") != integrated
        or shield.get("p2_status") != "LOCKED"
        or shield.get("owner_runtime_go") is not False
        or not isinstance(swus, list) or len(swus) != 16
        or {s.get("task_id") for s in swus if isinstance(s, dict)} != ext_ids
        or any(s.get("source_status") != next(
                 m["code_status"] for m in extension if m["id"] == s.get("task_id"))
               for s in swus if isinstance(s, dict))):
        raise ValueError("CodeShield feature queue does not match integrated inventory")
    if active_count + integrated > 55:
        raise ValueError("unexpected source integration scope")
    if not all(
        isinstance(m.get("allowed_paths"), list) and m["allowed_paths"]
        and all(_source_file_exists(root, p) for p in m["allowed_paths"])
        for m in extension if m.get("integrated_into_dev")
    ):
        raise ValueError("invalid CodeShield SWU crosswalk")
    # Integrated source candidates do not establish real OS/F18/owner trust.
    return {
        "v13_implementation_source_swu_completed": active_count + integrated,
        "v13_implementation_source_swu_total": 55,
        "v13_implementation_source_swu_percent": round((active_count + integrated) * 100 / 55, 2),
        "legacy_mla_source_swu_completed": active_count,
        "legacy_mla_source_swu_total": 39,
        "codeshield_feature_source_candidates_at_merge": staged,
        "codeshield_feature_swu_total": 16,
        "codeshield_source_candidates_integrated_into_dev": integrated,
        "codeshield_feature_source_head_snapshot": record["code_shield_feature_head_at_rebaseline"],
        "integration": "SOURCE_MERGED_P1_UNVERIFIED",
        "source_design_sha": zero_vm["design_sha"],
        "remaining_source_swu": 55 - active_count - integrated,
        "zero_vm_container_dependency": False,
        "source_sha_independently_attested": False,
        "high_p2_accepted": False,
        "p2": "LOCKED",
        "verification": "UNASSESSED",
        "execution_allowed": False,
        "owner_go_verified": False,
        "independent_f18_verified": False,
    }


def load_local_operator_swu_progress(root: Path, base: dict) -> dict:
    """New add-on counters; never rewrite original V1.3 55-SWU audit."""
    record = read_local_metadata(root / "docs" / "WINDOWS_LOCAL_OPERATOR_SWU_QUEUE.json")
    expected = {"MLA-OP-SWU-001", "MLA-OP-SWU-002", "MLA-OP-SWU-003"}
    if (type(record) is not dict or record.get("schema") != "mla-local-op-swu/v1"
        or record.get("project") != "hibi89/my_local_ai"
        or record.get("p1_source_swu_total") != 3
        or record.get("p2") != "LOCKED" or record.get("verified_rate") != "UNASSESSED"
        or record.get("owner_go") is not False
        or type(record.get("p2_accepted_swu")) is not int
        or record["p2_accepted_swu"] != 0
        or type(record.get("tasks")) is not list or len(record["tasks"]) != 3):
        raise ValueError("invalid Local Operator SWU inventory")
    ids, completed = set(), 0
    for task in record["tasks"]:
        if (type(task) is not dict or task.get("id") not in expected
            or task["id"] in ids
            or task.get("code_status") not in {"READY_CODE_ONLY", "SOURCE_COMPLETE_P2_PENDING"}
            or task.get("verified") is not False
            or task.get("owner_go") is not False
            or type(task.get("allowed_paths")) is not list
            or not task["allowed_paths"]):
            raise ValueError("inconsistent Local Operator evidence")
        ids.add(task["id"])
        if task["code_status"] == "SOURCE_COMPLETE_P2_PENDING":
            if any(not _source_file_exists(root, p) for p in task["allowed_paths"]):
                raise ValueError("missing Local Operator source")
            completed += 1
    if ids != expected or completed != record.get("p1_source_swu_completed"):
        raise ValueError("stale Local Operator counts")
    total = base["v13_implementation_source_swu_total"] + 3
    done = base["v13_implementation_source_swu_completed"] + completed
    return {
        "local_op_p1_swu_completed": completed,
        "local_op_p1_swu_total": 3,
        "local_op_p1_source_percent": round(completed * 100 / 3, 2),
        "overall_p1_source_swu_completed": done,
        "overall_p1_source_swu_total": total,
        "overall_p1_source_swu_percent": round(done * 100 / total, 2),
        "overall_p2_swu_accepted": 0,
        "overall_p2_swu_total": total,
        "overall_p2_swu_recorded_pass_percent": 0.0,
        "overall_p2_formal_verified_rate": "UNASSESSED",
        "local_op_windows_real_test": "NOT_RUN",
        "local_op_arbitrary_shell_authorized": False,
        "local_op_privileged_execution_authorized": False,
        "p2": "LOCKED",
    }
