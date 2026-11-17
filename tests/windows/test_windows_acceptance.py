"""Owner Windows 11 acceptance source-only, never executed in P1.

No admin calls, no Windows Sandbox feature enablement, no real device code
execution, and no independent audit claim without a separately trusted runner.
"""
from __future__ import annotations
import unittest


WINDOWS_ACCEPTANCE=(
    "P2-WIN-001 actual Windows 11 owner OS build and reparse/hardlink attacks",
    "P2-WIN-002 offline exact Qwen model and OpenCode binary provenance",
    "P2-WIN-003 Windows Sandbox isolated coder vs protected reviewer identity",
    "P2-WIN-004 no protected HMAC owner key accessible from coding guest",
    "P2-WIN-005 network egress DENY from coder and independent reviewer",
    "P2-WIN-006 revoked/expired owner GO denies every protected operation",
    "P2-WIN-007 guest-created VERIFIED receipt never promotes protected ref",
    "P2-WIN-008 actual interrupted SQLite WAL/run/restart lease fencing",
    "P2-WIN-009 original/main Git SHA unchanged on candidate failure",
    "P2-WIN-010 real 24h load, temperatures, RAM/VRAM and disk thresholds",
)


class OwnerWindowsAcceptanceTests(unittest.TestCase):
    @unittest.skip("P2_LOCKED: real owner Windows Sandbox and Qwen NOT_RUN")
    def test_windows_hardware_and_isolation(self):
        self.fail("Must supply independent host attestation and owner device")

    @unittest.skip("P2_LOCKED: actual 24h unattended endurance NOT_RUN")
    def test_windows_unattended_24h(self):
        self.fail("Must measure actual owner hardware, thermal and persistence")


if __name__=="__main__":
    unittest.main()
