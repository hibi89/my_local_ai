"""Owner Windows 11 acceptance source-only, never executed in P1.

No admin calls, virtualization changes, real device code
execution, and no independent audit claim without a separately trusted runner.
"""
from __future__ import annotations
import unittest
import re


WINDOWS_ACCEPTANCE=(
    "P2-WIN-001 actual Windows 11 owner OS build and reparse/hardlink attacks",
    "P2-WIN-002 offline exact Qwen model and OpenCode binary provenance",
    "P2-WIN-003 distinct protected Windows service and OwnerUI principals with pinned CNG keys",
    "P2-WIN-004 protected owner signer key inaccessible from the Controller account",
    "P2-WIN-005 loopback-only model transport and independent evidence of typed operator egress denial",
    "P2-WIN-006 revoked/expired owner GO denies every protected operation",
    "P2-WIN-007 guest-created VERIFIED receipt never promotes protected ref",
    "P2-WIN-008 actual interrupted SQLite WAL/run/restart lease fencing",
    "P2-WIN-009 original/main Git SHA unchanged on candidate failure",
    "P2-WIN-010 real 24h load, temperatures, RAM/VRAM and disk thresholds",
)


class OwnerWindowsAcceptanceTests(unittest.TestCase):
    @unittest.skip("P2_LOCKED: real owner Windows protection and Qwen NOT_RUN")
    def test_windows_hardware_and_isolation(self):
        self.fail("Must supply independent host attestation and owner device")

    @unittest.skip("P2_LOCKED: actual 24h unattended endurance NOT_RUN")
    def test_windows_unattended_24h(self):
        self.fail("Must measure actual owner hardware, thermal and persistence")


if __name__=="__main__":
    unittest.main()



def authored_windows_evidence_manifest(gates: dict, exact_sha: str | None) -> tuple[dict, ...]:
    """Exact-SHA owner Windows evidence schema; source-only and always NOT_RUN.

    Runs as a read-only schema check with current privileges.
    Real OS principal isolation, model output, protected owner signer and
    physical 24-hour evidence require a separately authorized runner in P2.
    """
    if not isinstance(gates,dict):
        raise ValueError("invalid phase gates")
    p1,p2=gates.get("p1"),gates.get("p2")
    sha_valid=isinstance(exact_sha,str) and re.fullmatch(r"[0-9a-f]{40}",exact_sha) is not None
    ready=bool(
        sha_valid and isinstance(p1,dict) and isinstance(p2,dict)
        and gates.get("current_phase")=="P2_VERIFICATION"
        and p1.get("implementation_complete_candidate") is True
        and p1.get("high_approved_candidate") is True
        and type(p1.get("code_req_completed")) is int and p1["code_req_completed"]==30
        and type(p1.get("code_req_total")) is int and p1["code_req_total"]==30
        and p1.get("implementation_sha")==exact_sha
        and p2.get("status")=="P2_VERIFICATION"
    )
    return tuple({
        "scenario_id":item.split()[0],
        "description":" ".join(item.split()[1:]),
        "implementation_sha":exact_sha if ready else None,
        "p2_gate_ready":ready,
        "owner_windows_result":"NOT_RUN",
        "trusted_reviewer_os_result":"NOT_RUN",
        "model_real_invocation_result":"NOT_RUN",
        "source_and_main_sha_unchanged":"NOT_RUN",
        "owner_runner_evidence_sha":None,
        "requires_owner_controlled_runner":True,
        "automatic_host_fallback":False,
        "can_promote":False,
    } for item in WINDOWS_ACCEPTANCE)
