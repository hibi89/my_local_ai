"""Local Operator P1 syntax and deny checks; not Windows P2 evidence."""
import json
import ctypes
import sys
import types
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
               '{"schema":"mla-local-operator/v1","action":"cng-provider-status","key":"export"}',
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
             patch.object(op, "_protected_path_status", return_value={"state": "NOT_PRESENT"}), \
             patch.object(op, "_cng_provider_status", return_value={"state": "READ_ONLY_RESULT"}):
            result = op.run_operator_request("MLA 보안 환경 진단")
        self.assertEqual(result["state"], "READ_ONLY_RESULT")
        self.assertEqual(len(result["checks"]), 4)
        self.assertFalse(result["os_settings_changed"])
        self.assertFalse(result["arbitrary_shell_executed"])
        self.assertFalse(result["execution_authority_granted"])

    def test_probe_failure_is_bounded_hold(self):
        with patch.object(op.os, "name", "nt"), \
             patch.object(op, "_tpm_status", side_effect=OSError("PRIVATE-SECRET")):
            result = op.run_operator_request("TPM 상태 확인")
        self.assertEqual(result["state"], "HOLD_PARTIAL")
        self.assertNotIn("PRIVATE-SECRET", json.dumps(result))

    def test_cng_alias_is_readonly_and_never_a_grant(self):
        self.assertEqual(op.parse_operator_request("CNG 서명 공급자 확인"),
                         "cng-provider-status")
        self.assertIn("cng-provider-status", op.operator_catalog()["allowed_actions"])
        with patch.object(op.os, "name", "nt"), \
             patch.object(op, "_cng_provider_status", return_value={
                 "state": "READ_ONLY_RESULT", "protected_trust_verified": False,
                 "key_provisioned_verified": False
             }):
            result = op.run_operator_request("CNG 서명 공급자 확인")
        self.assertEqual(result["state"], "READ_ONLY_RESULT")
        self.assertFalse(result["execution_authority_granted"])
        self.assertFalse(result["checks"]["cng-provider-status"]["key_provisioned_verified"])

    def _simulate_native_cng(self, *, implementation=2, pin="missing", kind=1,
                             open_status=0):
        events = []
        reg = types.ModuleType("winreg")
        reg.HKEY_LOCAL_MACHINE, reg.KEY_READ, reg.KEY_WOW64_64KEY, reg.REG_SZ = 1, 2, 4, 1
        class Key:
            def __enter__(self): return self
            def __exit__(self, *args): return False
        def key_open(root, path, reserved, access):
            events.append(("registry_read", root, access))
            if pin == "missing":
                raise FileNotFoundError()
            if pin == "denied":
                raise PermissionError("PRIVATE_KEY_PATH_NOT_TO_EXPOSE")
            if pin == "other_oserror":
                raise OSError("INTERNAL_SENSITIVE_DETAILS")
            return Key()
        def value_read(key, name):
            events.append(("value_read", name))
            return pin, kind
        reg.OpenKey, reg.QueryValueEx = key_open, value_read
        class Func:
            def __init__(self, name):
                self.name = name
            def __call__(self, *args):
                events.append((self.name, *[str(x)[:60] for x in args if isinstance(x,str)]))
                if self.name == "open":
                    if open_status == 0:
                        args[0]._obj.value = 501
                    self.assert_called = True
                    return open_status
                if self.name == "get":
                    args[2]._obj.value = implementation
                    args[4]._obj.value = 4
                    return 0
                if self.name == "free":
                    return 0
        fake = types.SimpleNamespace(
            NCryptOpenStorageProvider=Func("open"),
            NCryptGetProperty=Func("get"),
            NCryptFreeObject=Func("free"),
        )
        return reg, lambda *args, **kwargs: fake, events

    def test_cng_native_open_is_only_provider_property_and_free(self):
        reg, native, events = self._simulate_native_cng()
        with patch.dict(sys.modules, {"winreg": reg}), \
             patch.object(ctypes, "WinDLL", native, create=True):
            result = op._cng_provider_status()
        self.assertEqual(result["state"], "READ_ONLY_RESULT")
        self.assertEqual(result["profile"], "NOT_CONFIGURED")
        self.assertTrue(result["software_ksp_available"])
        self.assertFalse(result["profile_enabled"])
        self.assertFalse(result["key_provisioned_verified"])
        self.assertFalse(result["protected_trust_verified"])
        self.assertEqual([ev[0] for ev in events if ev[0] in ("open","get","free")],
                         ["open","get","free"])
        self.assertFalse(any("NCryptOpenKey" in str(ev) for ev in events))

    def test_cng_provisioned_pin_remains_untrusted(self):
        reg, native, events = self._simulate_native_cng(
            pin="SOFTWARE_CNG_OWNER_APPROVED_V1")
        with patch.dict(sys.modules, {"winreg": reg}), \
             patch.object(ctypes, "WinDLL", native, create=True):
            result = op._cng_provider_status()
        self.assertEqual(result["state"], "READ_ONLY_RESULT")
        self.assertTrue(result["profile_enabled"])
        self.assertFalse(result["key_provisioned_verified"])

    def test_cng_unknown_pin_or_wrong_provider_fails_closed(self):
        for config in (
            {"pin": "Microsoft Software Key Storage Provider"},
            {"pin": "SOFTWARE_CNG_OWNER_APPROVED_V1", "kind": 4},
            {"implementation": 1}, {"implementation": 3},
            {"implementation": 8}, {"open_status": 1},
        ):
            with self.subTest(config=config):
                reg, native, events = self._simulate_native_cng(**config)
                with patch.dict(sys.modules, {"winreg": reg}), \
                     patch.object(ctypes, "WinDLL", native, create=True):
                    result = op._cng_provider_status()
                self.assertTrue(result["state"].startswith("HOLD_"))
                self.assertFalse(result["protected_trust_verified"])
                self.assertFalse(result["key_provisioned_verified"])
                if any(e[0] == "open" and config.get("open_status", 0) == 0
                       for e in events):
                    self.assertTrue(any(e[0] == "free" for e in events))


    def test_cng_denied_registry_still_checks_provider_without_grant(self):
        reg, native, events = self._simulate_native_cng(pin="denied")
        with patch.dict(sys.modules, {"winreg": reg}), \
             patch.object(ctypes, "WinDLL", native, create=True):
            result = op._cng_provider_status()
        self.assertEqual(result["state"], "HOLD_PIN_ACCESS_DENIED")
        self.assertEqual(result["ksp_state"], "READ_ONLY_RESULT")
        self.assertTrue(result["software_ksp_available"])
        self.assertFalse(result["profile_enabled"])
        self.assertFalse(result["protected_trust_verified"])
        self.assertFalse(result["key_provisioned_verified"])
        self.assertFalse(result["runtime_authorized"])
        self.assertEqual([e[0] for e in events if e[0] in ("open","get","free")],
                         ["open","get","free"])
        self.assertNotIn("PRIVATE_KEY_PATH_NOT_TO_EXPOSE", json.dumps(result))

    def test_cng_registry_and_provider_errors_stay_independent(self):
        for kwargs, expected, available in (
            ({"pin": "denied", "open_status": 1},
             "HOLD_PIN_ACCESS_DENIED", False),
            ({"pin": "other_oserror"}, "HOLD_PIN_UNREADABLE", True),
            ({"pin": "SOFTWARE_CNG_OWNER_APPROVED_V1", "kind": 4},
             "HOLD_PIN_INVALID", True),
        ):
            with self.subTest(kwargs=kwargs):
                reg, native, events = self._simulate_native_cng(**kwargs)
                with patch.dict(sys.modules, {"winreg": reg}), \
                     patch.object(ctypes, "WinDLL", native, create=True):
                    result = op._cng_provider_status()
                self.assertEqual(result["state"], expected)
                self.assertEqual(result["software_ksp_available"], available)
                self.assertFalse(result["profile_enabled"])
                self.assertFalse(result["protected_trust_verified"])
                self.assertFalse(result["key_provisioned_verified"])
                self.assertIn("ksp_state", result)
                self.assertNotIn("INTERNAL_SENSITIVE_DETAILS", json.dumps(result))



if __name__ == "__main__":
    unittest.main()
