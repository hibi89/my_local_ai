"""P2 owner Windows F18 checklist harness. NOT_RUN by default.

This file is authored in P1 as a contract. It does not switch Windows
features, launch Sandbox, run binaries, touch secrets or claim F18 PASS.
Synthetic arguments cannot prove independently protected OS principals.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unittest

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class OwnerWindowsAttestationInputs:
    source_sha: str
    candidate_sha: str
    plan_sha256: str
    coder_principal: str
    reviewer_principal: str
    owner_signer_principal: str
    windows_sandbox_available: bool
    network_egress_denied: bool
    guest_readback_of_signer_denied: bool
    actual_owner_test_executed: bool


@dataclass(frozen=True)
class WindowsBoundaryPrecheck:
    missing_controls: tuple[str, ...]
    status: str = "P2_NOT_RUN_INDEPENDENT_EVIDENCE_REQUIRED"
    can_issue_trusted_receipt: bool = False
    can_promote_local_ref: bool = False


def precheck_owner_windows_boundary(data: OwnerWindowsAttestationInputs) -> WindowsBoundaryPrecheck:
    """A structural checklist, NOT a real OS isolation attestation."""
    if not isinstance(data,OwnerWindowsAttestationInputs):
        raise ValueError("invalid Windows evidence structure")
    if (not isinstance(data.source_sha,str) or not _SHA40.fullmatch(data.source_sha)
        or not isinstance(data.candidate_sha,str) or not _SHA40.fullmatch(data.candidate_sha)
        or data.source_sha == data.candidate_sha
        or not isinstance(data.plan_sha256,str) or not _SHA64.fullmatch(data.plan_sha256)):
        raise ValueError("invalid pinned Windows SHA")
    principals=(data.coder_principal,data.reviewer_principal,data.owner_signer_principal)
    if any(not isinstance(x,str) or not x or len(x)>128 or x != x.strip()
           or any(ord(ch)<32 or ord(ch)==127 for ch in x) for x in principals):
        raise ValueError("missing or unsafe Windows principals")
    problems=[]
    # Windows account names and SIDs are not case-sensitive attestations.
    if len({x.casefold() for x in principals})!=3:
        problems.append("PRINCIPAL_SEPARATION")
    if any(type(x) is not bool for x in (
        data.windows_sandbox_available, data.network_egress_denied,
        data.guest_readback_of_signer_denied, data.actual_owner_test_executed
    )):
        raise ValueError("untrusted Windows control type")
    if data.windows_sandbox_available is not True:
        problems.append("ISOLATED_SANDBOX")
    if data.network_egress_denied is not True:
        problems.append("EGRESS_ISOLATION")
    if data.guest_readback_of_signer_denied is not True:
        problems.append("OWNER_SIGNER_PROTECTION")
    if data.actual_owner_test_executed is not True:
        problems.append("OWNER_WINDOWS_REAL_TEST")
    # A guest can fabricate every field above. The controller still needs a
    # separately authenticated OS test transcript and protected signer check.
    return WindowsBoundaryPrecheck(tuple(problems))


class OwnerWindowsRealF18Tests(unittest.TestCase):
    @unittest.skip("P2_LOCKED: owner Windows Sandbox actual independent F18 NOT_RUN")
    def test_real_isolated_coder_cannot_read_signer_or_reviewer(self):
        self.fail("Requires separately approved owner Windows OS test runner")

    @unittest.skip("P2_LOCKED: independent verifier and protected ref CAS NOT_RUN")
    def test_real_guest_receipt_replay_and_host_ref_promotion(self):
        self.fail("Requires actual protected environment and exact SHA evidence")


if __name__=="__main__":
    unittest.main()



class WindowsBoundaryContractTests(unittest.TestCase):
    def sample(self, **changes):
        opts=dict(
            source_sha="a"*40,candidate_sha="b"*40,plan_sha256="c"*64,
            coder_principal="NT-USER-CODER",
            reviewer_principal="NT-USER-REVIEWER",
            owner_signer_principal="NT-OWNER-SIGNER",
            windows_sandbox_available=True,network_egress_denied=True,
            guest_readback_of_signer_denied=True,actual_owner_test_executed=True,
        )
        opts.update(changes)
        return OwnerWindowsAttestationInputs(**opts)

    def test_even_all_claimed_controls_can_never_mint_f18(self):
        value=precheck_owner_windows_boundary(self.sample())
        self.assertEqual(value.missing_controls,())
        self.assertEqual(value.status,"P2_NOT_RUN_INDEPENDENT_EVIDENCE_REQUIRED")
        self.assertFalse(value.can_issue_trusted_receipt)
        self.assertFalse(value.can_promote_local_ref)

    def test_casefold_alias_of_principal_does_not_count_as_separate_reviewer(self):
        value=precheck_owner_windows_boundary(self.sample(
            reviewer_principal="nt-user-coder",
        ))
        self.assertIn("PRINCIPAL_SEPARATION",value.missing_controls)

    def test_invalid_pins_controls_and_principal_escapes_denied(self):
        for variant in (
            {"candidate_sha":"a"*40},
            {"source_sha":"bad"},
            {"plan_sha256":"f"},
            {"coder_principal":"NT-USER-CODER\nOTHER"},
            {"reviewer_principal":" reviewer "},
            {"windows_sandbox_available":1},
            {"network_egress_denied":"true"},
        ):
            with self.subTest(variant=variant),self.assertRaises(ValueError):
                precheck_owner_windows_boundary(self.sample(**variant))
