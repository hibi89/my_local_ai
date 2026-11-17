"""P2 owner journey scenarios authored in P1, deliberately NOT auto-executed.

Do not add to the P1 synthetic CI. Real Playwright/keyboard/console/runtime
tests are locked until exact implementation SHA + High gate + owner consent.
"""
from __future__ import annotations
import unittest
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[2]

SCENARIOS=(
    ("P2-E2E-001","owner loads local app; no remote network"),
    ("P2-E2E-002","open plan with exact source SHA; P1 progress visible"),
    ("P2-E2E-003","optional EAI OFF does not change DAG and coding proposal"),
    ("P2-E2E-011","optional EAI exact-plan hints fail closed and never gain runtime authority"),
    ("P2-E2E-004","owner GO scope shows separate local vs remote action"),
    ("P2-E2E-005","untrusted coder patch cannot touch original checkout"),
    ("P2-E2E-006","independent F18 review rejects forged self PASS"),
    ("P2-E2E-007","isolated local ref CAS preserves original/main"),
    ("P2-E2E-008","interrupted/expired run remains HOLD and lease fenced"),
    ("P2-E2E-009","remote publish without separate owner GO denied"),
    ("P2-E2E-010","console errors/accessibility/responsive keyboard checked"),
    ("P2-E2E-012","loopback dashboard GET/HEAD only; blocked cross-origin and POST requests"),
    ("P2-E2E-013","status and synthetic evidence accurately label HOLD/NOT_RUN, never real F18 PASS"),
)


def p2_gate_ready(gates: dict, exact_sha: str) -> bool:
    """Static condition only, not authorization to perform actions."""
    if (not isinstance(gates,dict) or not isinstance(exact_sha,str)
        or re.fullmatch(r"[0-9a-f]{40}",exact_sha) is None
        or gates.get("current_phase") != "P2_VERIFICATION"):
        return False
    p1,p2=gates.get("p1"),gates.get("p2")
    if not isinstance(p1,dict) or not isinstance(p2,dict):
        return False
    return (
        type(p1.get("code_req_total")) is int
        and p1.get("code_req_total")==30
        and type(p1.get("code_req_completed")) is int
        and p1.get("code_req_completed")==30
        and p1.get("implementation_complete_candidate") is True
        and p1.get("high_approved_candidate") is True
        and p1.get("implementation_sha")==exact_sha
        and p2.get("status")=="P2_VERIFICATION"
        and p2.get("verified_sha") in (None, exact_sha)
    )


class OwnerJourneyP2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This suite intentionally never starts Playwright, a model, a local
        # app, Git, Windows security features or a real device in P1.
        gates=json.loads((ROOT/"WORK_PHASE_GATES.json").read_text(encoding="utf-8"))
        candidate=gates.get("p1",{}).get("implementation_sha")
        if not p2_gate_ready(gates,candidate):
            raise unittest.SkipTest("P2_LOCKED: owner E2E browser/runtime NOT_RUN")
        # Even if the gate is later opened, a protected owner-runner must
        # explicitly implement these tests; never silently report PASS.
        raise unittest.SkipTest("P2_OWNER_RUNNER_AND_EXACT_SHA_NOT_CONFIGURED")

    def test_owner_workflow_requires_real_browser_and_reviewer(self):
        self.fail("Owner-approved real browser/Windows fixture required")


if __name__=="__main__":
    unittest.main()



def authored_owner_evidence_manifest(gates: dict, exact_sha: str | None) -> tuple[dict, ...]:
    """P1 source-only checklist. No mocked fixture can claim a P2 test PASS."""
    ready = p2_gate_ready(gates, exact_sha)
    return tuple({
        "scenario_id": code,
        "description": description,
        "implementation_sha": exact_sha if ready else None,
        "p2_gate_ready": ready,
        "owner_real_browser_result": "NOT_RUN",
        "browser_console_result": "NOT_RUN",
        "browser_network_result": "NOT_RUN",
        "keyboard_a11y_result": "NOT_RUN",
        "responsive_result": "NOT_RUN",
        "inspected_browser_name": None,
        "observed_url": None,
        "owner_runner_evidence_sha": None,
        "trusted_f18_result": "NOT_RUN",
        "requires_owner_controlled_runner": True,
        "may_update_original": False,
        "may_publish": False,
    } for code, description in SCENARIOS)



def assert_p2_evidence_is_pending(gates: dict, exact_sha: str | None) -> None:
    """P1 contract check: no authored browser fixture may forge measured PASS."""
    rows=authored_owner_evidence_manifest(gates,exact_sha)
    if len({row["scenario_id"] for row in rows}) != len(SCENARIOS):
        raise ValueError("duplicate owner P2 scenario")
    for row in rows:
        if (row["owner_real_browser_result"] != "NOT_RUN"
            or row["trusted_f18_result"] != "NOT_RUN"
            or row["browser_console_result"] != "NOT_RUN"
            or row["browser_network_result"] != "NOT_RUN"
            or row["keyboard_a11y_result"] != "NOT_RUN"
            or row["responsive_result"] != "NOT_RUN"
            or row["owner_runner_evidence_sha"] is not None
            or row["may_update_original"] or row["may_publish"]
            or row["requires_owner_controlled_runner"] is not True):
            raise ValueError("P1 evidence fixture cannot assert owner/P2 results")
