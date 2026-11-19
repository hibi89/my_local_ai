"""P1 synthetic checks for owner-approved TPM-less CNG profile.

No registry/key/service/ACL mutation. Not native Windows proof or P2.
"""
import inspect
import sys
import types
import unittest
from unittest.mock import patch

from my_local_ai.state import consent as c


class CngKspProfileTests(unittest.TestCase):
    def test_explicit_profile_and_legacy_default_are_fixed(self):
        self.assertEqual(c._pinned_cng_provider("TPM_V1"),
                         "Microsoft Platform Crypto Provider")
        self.assertEqual(c._pinned_cng_provider("SOFTWARE_CNG_OWNER_APPROVED_V1"),
                         "Microsoft Software Key Storage Provider")
        for bad in ("", "Microsoft Software Key Storage Provider", "SOFTWARE",
                    "DEFAULT", "TPM_V1 ", 0, False, None, {}, []):
            with self.subTest(value=bad), self.assertRaises(c.ProtectedBrokerHold):
                c._pinned_cng_provider(bad)

    def test_hardware_implementation_required_for_tpm_profile(self):
        c._require_cng_capabilities("TPM_V1", 0x1)
        for flags in (0, 0x2, 0x3, None, True):
            with self.subTest(flags=flags), self.assertRaises(c.ProtectedBrokerHold):
                c._require_cng_capabilities("TPM_V1", flags)

    def test_software_implementation_requires_machine_signonly_and_acl(self):
        check = lambda **kw: c._require_cng_capabilities(
            "SOFTWARE_CNG_OWNER_APPROVED_V1", 0x2,
            key_type=0x20, key_usage=2, security_descriptor_supported=1, **kw)
        check()
        variations = (
            {"implementation": 0}, {"implementation": 0x1},
            {"implementation": 0x3}, {"implementation": 0xA},
            {"key_type": 0}, {"key_type": 0x20 | 1},
            {"key_type": False}, {"key_usage": 0xFFFFFF},
            {"key_usage": 0}, {"key_usage": False},
            {"security_descriptor_supported": 0},
            {"security_descriptor_supported": True},
        )
        for changed in variations:
            args = dict(mode="SOFTWARE_CNG_OWNER_APPROVED_V1", implementation=0x2,
                        key_type=0x20, key_usage=2,
                        security_descriptor_supported=1)
            args.update(changed)
            with self.subTest(change=changed), self.assertRaises(c.ProtectedBrokerHold):
                c._require_cng_capabilities(**args)

    def _registry(self, value=None, kind=1, missing=False):
        reg = types.ModuleType("winreg")
        reg.HKEY_LOCAL_MACHINE = 1
        reg.KEY_READ = 0x20019
        reg.KEY_WOW64_64KEY = 0x100
        reg.REG_SZ = 1

        class Key:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __int__(self): return 123
        calls = []
        def open_key(hive, path, reserved, rights):
            calls.append((hive, path, rights))
            return Key()
        def read(key, name):
            if missing:
                raise FileNotFoundError()
            return value, kind
        reg.OpenKey, reg.QueryValueEx = open_key, read
        class API:
            def check_acl(self, handle, kind, write_mask):
                calls.append(("acl", handle, kind, write_mask))
        return reg, API(), calls

    def test_no_unpinned_software_fallback_when_registry_pin_absent(self):
        reg, api, calls = self._registry(missing=True)
        with patch.dict(sys.modules, {"winreg": reg}):
            self.assertEqual(c._read_pinned_cng_mode(api), "TPM_V1")
        self.assertTrue(any(x[0] == "acl" for x in calls))

    def test_explicit_software_pin_and_nonstring_registry_denial(self):
        reg, api, _ = self._registry("SOFTWARE_CNG_OWNER_APPROVED_V1")
        with patch.dict(sys.modules, {"winreg": reg}):
            self.assertEqual(c._read_pinned_cng_mode(api),
                             "SOFTWARE_CNG_OWNER_APPROVED_V1")
        for value, kind in (("Unknown", 1), ("SOFTWARE_CNG_OWNER_APPROVED_V1", 4),
                            (False, 1), ("TPM_V1 ", 1)):
            reg, api, _ = self._registry(value, kind)
            with patch.dict(sys.modules, {"winreg": reg}):
                with self.subTest(value=value, kind=kind):
                    with self.assertRaises(c.ProtectedBrokerHold):
                        c._read_pinned_cng_mode(api)

    def test_signer_requires_live_hklm_pin_and_no_provider_switch(self):
        src = inspect.getsource(c._WindowsProtectedServiceAPI.signer)
        self.assertIn('_read_pinned_cng_mode(self) != mode', src)
        self.assertIn('_pinned_cng_provider(mode)', src)
        self.assertIn('dword(provider, "Impl Type")', src)
        self.assertIn('self._key_acl(prop("Security Descr"', src)
        self.assertIn('public.raw != self.roots[self.role][2]', src)
        self.assertNotIn('except ProtectedBrokerHold: open_provider', src)
        self.assertNotIn('NCryptCreatePersistedKey', src)
        self.assertNotIn('NCryptSetProperty', src)


if __name__ == "__main__":
    unittest.main()
