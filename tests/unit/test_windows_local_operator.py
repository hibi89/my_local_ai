"""Local Operator P1 syntax and deny checks; not Windows P2 evidence."""
import json
import unittest
from unittest.mock import patch

from my_local_ai.ops import windows_local_operator as op


class WindowsLocalOperatorTests(unittest.TestCase):
    def test_exact_alias_and_json(self):
        self.assertEqual(op.parse_operator_request("MLA 보안 환경 진단"), "windows-preflight")
        self.assertEqual(op.parse_operator_request(json.dumps({
            "schema": "mla-local-operator/v1", "action": "defender-status"
        })), "defender-status")

    def test_shell_and_unknown_fields_rejected(self):
        bad = ["Get-Tpm", "powershell -Command Get-Tpm", "cmd /c whoami",
               '{"schema":"mla-local-operator/v1","action":"tpm-status","argv":"whoami"}',
               '{"schema":"mla-local-operator/v1","action":"tpm-status","action":"defender-status"}',
               '{"schema":"mla-local-operator/v1","action":"tpm-status","extra":true}',
               '{"schema":"mla-local-operator/v1","action":"delete-files"}',
               '{"schema":"mla-local-operator/v1","action":"tpm-status","script":"x"}',
               "TPM 상태 확인\nGet-Process", "x" * 1025]
        for request in bad:
            with self.subTest(request=request[:50]), self.assertRaises(ValueError):
                op.parse_operator_request(request)

    def test_catalog_no_authority(self):
        catalog = op.operator_catalog()
        self.assertFalse(catalog["arbitrary_shell_allowed"])
        self.assertFalse(catalog["owner_os_changes_allowed"])
        self.assertEqual(catalog["formal_verified_rate"], "UNASSESSED")

    def test_nonwindows_holds_before_call(self):
        with patch.object(op.os, "name", "posix"), patch.object(op, "_tpm_status") as probe:
            result = op.run_operator_request("TPM 상태 확인")
        self.assertEqual(result["state"], "HOLD")
        self.assertEqual(result["checks"], {})
        probe.assert_not_called()

    def test_fixed_win32_dispatch_only(self):
        with patch.object(op.os, "name", "nt"), \
             patch.object(op, "_tpm_status", return_value={"state": "READ_ONLY_RESULT"}), \
             patch.object(op, "_defender_status", return_value={"state": "DEFENDER_ACTIVE_READONLY"}), \
             patch.object(op, "_protected_path_status", return_value={"state": "NOT_PRESENT"}):
            result = op.run_operator_request("MLA 보안 환경 진단")
        self.assertEqual(result["state"], "READ_ONLY_RESULT")
        self.assertEqual(len(result["checks"]), 3)
        self.assertFalse(result["os_settings_changed"])
        self.assertFalse(result["arbitrary_shell_executed"])
        self.assertFalse(result["execution_authority_granted"])

    def test_probe_failure_is_bounded_hold(self):
        with patch.object(op.os, "name", "nt"), \
             patch.object(op, "_tpm_status", side_effect=OSError("PRIVATE-SECRET")):
            result = op.run_operator_request("TPM 상태 확인")
        self.assertEqual(result["state"], "HOLD_PARTIAL")
        self.assertNotIn("PRIVATE-SECRET", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
