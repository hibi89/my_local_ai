"""Synthetic safety tests for staged Windows images, with no native OS writes."""
from contextlib import redirect_stdout
import io
from pathlib import Path
from unittest.mock import patch
import json
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import build_protected_windows as builder
import preflight_protected_windows as preflight


def pins_for(installed: Path, images: dict) -> dict:
    roles = {}
    for i, role in enumerate(preflight.SERVICE_ROLES, 1):
        name = preflight.IMAGE_BY_ROLE[role]
        roles[role] = {
            "sid": f"S-1-5-21-100-200-300-{1000+i}",
            "sha": images[name]["image_sha256"],
            "key": f"MyLocalAI.Test{i}",
            "public": b"ECS1\x20\x00\x00\x00" + bytes([i])*64,
            "image_path": str(installed / name / (name + ".exe")),
            "service_type": 0x10,
            "start": 3,
        }
    owner_name = preflight.IMAGE_BY_ROLE["owner-ui"]
    return {
        "controller_sid": "S-1-5-21-100-200-300-1000",
        "owner_sid": "S-1-5-21-100-200-300-1004",
        "owner_session": 2,
        "owner_ui_sha": images[owner_name]["image_sha256"],
        "owner_ui_key": "MyLocalAI.OwnerTest",
        "owner_ui_public": b"ECS1\x20\x00\x00\x00" + bytes([4])*64,
        "roles": roles,
    }


class ReadOnlyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bundle, self.installed = root / "staged", root / "installed"
        self.bundle.mkdir()
        self.installed.mkdir()
        self.images = {}
        self.base_manifest = {
            "schema": "mla-protected-bundle-inventory/v1",
            "trusted_or_installed": False,
            "os_accounts_keys_acl_service_changes": "NOT_PERFORMED",
            "windows_native_acceptance": "NOT_RUN",
            "python": "3.11",
            "pyinstaller": builder.PYINSTALLER_VERSION,
            "images": {},
        }
        for role, name, kind in builder.IMAGES:
            for folder in (self.bundle, self.installed):
                node = folder / name
                (node / "_internal").mkdir(parents=True)
                (node / (name + ".exe")).write_bytes(b"MZ-synthetic-" + role.encode())
                (node / "_internal" / "data.bin").write_bytes(b"fake-library-" + role.encode())
            observed = builder.inspect_image(self.bundle / name, name)
            self.images[name] = observed
            self.base_manifest["images"][role] = {
                "directory": name, "executable": name + ".exe",
                "scm_service": f"MyLocalAI.{role}.v1" if kind == "service" else None,
                **observed,
            }
        self.manifest = self.bundle / "UNTRUSTED_BUILD_MANIFEST.json"
        self.write_manifest()
        self.settings = pins_for(self.installed, self.images)

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.base_manifest), encoding="utf-8")

    def check(self, settings=None):
        return preflight.preflight(self.bundle, self.installed,
                                   settings=self.settings if settings is None else settings)

    def test_exact_matching_files_and_pins_still_hold(self):
        result = self.check()
        self.assertEqual(result["precheck"], "MATCHED_UNATTESTED")
        self.assertEqual(result["decision"], "HOLD")
        self.assertFalse(result["runtime_authorized"])
        self.assertFalse(result["owner_signature_verified"])
        self.assertFalse(result["independent_f18_verified"])
        self.assertFalse(result["defender_scan_verified"])
        self.assertEqual(len(result["image_sha256"]), 4)
        self.assertNotIn("S-1-5", json.dumps(result))

    def test_cli_never_returns_zero_even_when_static_pins_match(self):
        matched = self.check()
        with patch.object(preflight, "preflight", return_value=matched):
            with redirect_stdout(io.StringIO()) as stream:
                status = preflight.main(["--bundle", str(self.bundle),
                                         "--installed-root", str(self.installed)])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(stream.getvalue())["decision"], "HOLD")

    def test_modified_installed_executable_is_rejected(self):
        name = preflight.IMAGE_BY_ROLE["owner"]
        with (self.installed / name / (name + ".exe")).open("ab") as stream:
            stream.write(b"tamper")
        self.assertEqual(self.check()["code"], "STAGED_INSTALLED_HASH_MISMATCH")

    def test_modified_installed_dependency_is_rejected(self):
        name = preflight.IMAGE_BY_ROLE["reviewer"]
        (self.installed / name / "_internal" / "data.bin").write_bytes(b"tamper")
        self.assertEqual(self.check()["code"], "STAGED_INSTALLED_HASH_MISMATCH")

    def test_software_cng_profile_is_only_readonly_precheck(self):
        self.settings["key_provider_mode"] = "SOFTWARE_CNG_OWNER_APPROVED_V1"
        result = self.check()
        self.assertEqual(result["precheck"], "MATCHED_UNATTESTED")
        self.assertEqual(result["cng_provider_mode"], "SOFTWARE_CNG_OWNER_APPROVED_V1")
        self.assertFalse(result["cng_hardware_attested"])
        self.assertFalse(result["runtime_authorized"])
        self.assertEqual(result["decision"], "HOLD")

    def test_invalid_cng_profile_is_denied(self):
        self.settings["key_provider_mode"] = "Microsoft Software Key Storage Provider"
        self.assertEqual(self.check()["code"], "CNG_PROVIDER_PIN_INVALID")
        self.settings["key_provider_mode"] = False
        self.assertEqual(self.check()["code"], "CNG_PROVIDER_PIN_INVALID")

    def test_owner_key_or_image_pin_mismatch(self):
        self.settings["owner_ui_sha"] = "f"*64
        self.assertEqual(self.check()["code"], "OWNER_IMAGE_PIN_MISMATCH")
        self.settings["owner_ui_sha"] = self.images["MyLocalAI.OwnerUI"]["image_sha256"]
        self.settings["roles"]["scanner"]["public"] = self.settings["roles"]["owner"]["public"]
        self.assertEqual(self.check()["code"], "PRINCIPALS_OR_KEYS_NOT_INDEPENDENT")

    def test_duplicate_principal_or_sid_bypasses_never(self):
        self.settings["roles"]["reviewer"]["sid"] = self.settings["owner_sid"]
        self.assertEqual(self.check()["code"], "PRINCIPALS_OR_KEYS_NOT_INDEPENDENT")

    def test_service_path_arguments_or_autostart_rejected(self):
        self.settings["roles"]["scanner"]["image_path"] += " --unsafe"
        self.assertEqual(self.check()["code"], "SCM_IMAGE_PATH_MISMATCH")
        name = preflight.IMAGE_BY_ROLE["scanner"]
        self.settings["roles"]["scanner"]["image_path"] = str(
            self.installed / name / (name + ".exe"))
        self.settings["roles"]["scanner"]["start"] = 2
        self.assertEqual(self.check()["code"], "SERVICE_CONFIG_INVALID")

    def test_forged_duplicate_manifest_fields_rejected(self):
        src = self.manifest.read_text(encoding="utf-8")
        self.manifest.write_text('{"schema":"forged",' + src.lstrip()[1:],
                                 encoding="utf-8")
        self.assertEqual(self.check()["code"], "DUPLICATE_MANIFEST_KEY")

    def test_manifest_untrusted_flag_cannot_be_upgraded(self):
        self.base_manifest["trusted_or_installed"] = True
        self.write_manifest()
        self.assertEqual(self.check()["code"], "INVALID_MANIFEST")

    def test_staging_not_installed_or_missing_is_rejected(self):
        self.assertEqual(preflight.preflight(self.bundle, self.bundle,
            settings=self.settings)["code"], "STAGE_INSTALL_NOT_SEPARATE")
        self.assertEqual(preflight.preflight(self.bundle, self.installed / "missing",
            settings=self.settings)["precheck"], "BLOCKED")

    def test_hardlink_in_bundle_denied_where_supported(self):
        name = preflight.IMAGE_BY_ROLE["owner"]
        src = self.bundle / name / "_internal" / "data.bin"
        extra = Path(self.temp.name) / "hardlink.bin"
        try:
            import os
            os.link(src, extra)
        except OSError:
            self.skipTest("filesystem has no hardlink support")
        self.assertEqual(self.check()["code"], "INVALID_FROZEN_IMAGE")

    def test_native_preflight_never_claims_owner_pc_verification(self):
        # The GitHub Windows runner has no Owner-provisioned MLA services;
        # using no injected fixture must HOLD without writing any settings.
        result = preflight.preflight(self.bundle, self.installed)
        self.assertEqual(result["decision"], "HOLD")
        self.assertFalse(result["runtime_authorized"])



    def test_preflight_distinguishes_unreadable_pins_from_missing_components(self):
        for exc, code in (
            (PermissionError("private registry value"), "PREFLIGHT_ACCESS_DENIED"),
            (FileNotFoundError("private registry value"), "PREFLIGHT_COMPONENT_NOT_FOUND"),
        ):
            with self.subTest(code=code), patch.object(preflight, "_native_settings", side_effect=exc):
                result = preflight.preflight(self.bundle, self.installed)
            self.assertEqual(result["code"], code)
            self.assertFalse(result["runtime_authorized"])
            self.assertNotIn("private registry value", json.dumps(result))


class HostReadOnlyIntakeTests(unittest.TestCase):
    """Local synthetic probes; neither provisioning nor owner-device attestation."""

    def simulated_report(self):
        return {
            "read_only": True, "os_settings_changed": False,
            "execution_authority_granted": False,
            "checks": {
                "tpm-status": {"state": "READ_ONLY_RESULT", "tpm_present": False},
                "defender-status": {"state": "DEFENDER_ACTIVE_READONLY"},
                "protected-path-presence": {"state": "HOLD_PATH_UNAVAILABLE"},
                "cng-provider-status": {
                    "state": "READ_ONLY_RESULT",
                    "profile": "SOFTWARE_CNG_OWNER_APPROVED_V1",
                    "software_ksp_available": True,
                },
            },
        }

    def test_nonwindows_is_hold_and_does_not_probe(self):
        # Import before temporarily changing os.name on Windows; pathlib
        # must never be asked to instantiate an unsupported PosixPath.
        from my_local_ai.ops import windows_local_operator as local_op
        with patch.object(preflight.os, "name", "posix"), \
             patch.object(local_op, "run_operator_request") as probe:
            result = preflight.host_readonly_prerequisites()
        self.assertEqual(result["reason"], "WINDOWS_REQUIRED")
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["checks"], {})
        probe.assert_not_called()

    def test_successful_synthetic_host_probe_is_still_non_authoritative(self):
        with patch.object(preflight.os, "name", "nt"), \
             patch("my_local_ai.ops.windows_local_operator.run_operator_request",
                   return_value=self.simulated_report()) as probe:
            result = preflight.host_readonly_prerequisites()
        probe.assert_called_once_with("MLA 보안 환경 진단")
        self.assertEqual(result["precheck"], "OBSERVED_UNATTESTED")
        self.assertEqual(result["decision"], "HOLD")
        self.assertFalse(result["runtime_authorized"])
        self.assertFalse(result["owner_approval_verified"])
        self.assertFalse(result["protected_signer_verified"])
        self.assertEqual(result["cng_profile"], "SOFTWARE_CNG_OWNER_APPROVED_V1")
        serialized = json.dumps(result)
        self.assertNotIn("tpm_present", serialized)
        self.assertNotIn("S-1-5-", serialized)
        self.assertNotIn("PrivateKey", serialized)

    def test_malformed_or_privileged_operator_result_is_denied_without_leaks(self):
        for change in (
            {"read_only": False},
            {"os_settings_changed": True},
            {"execution_authority_granted": True},
            {"checks": {"arbitrary": {"state": "READ_ONLY_RESULT"}}},
            {"checks": {**self.simulated_report()["checks"],
                        "tpm-status": {"state": "PRIVATE_PASSWORD"}}},
        ):
            sample = {**self.simulated_report(), **change}
            with self.subTest(change=str(change)[:35]), \
                 patch.object(preflight.os, "name", "nt"), \
                 patch("my_local_ai.ops.windows_local_operator.run_operator_request",
                       return_value=sample):
                result = preflight.host_readonly_prerequisites()
            self.assertEqual(result["decision"], "HOLD")
            self.assertEqual(result["precheck"], "BLOCKED")
            self.assertEqual(result["checks"], {})
            self.assertNotIn("PRIVATE_PASSWORD", json.dumps(result))

    def test_probe_exception_redacted_and_never_authorized(self):
        with patch.object(preflight.os, "name", "nt"), \
             patch("my_local_ai.ops.windows_local_operator.run_operator_request",
                   side_effect=OSError("sensitive account name")):
            result = preflight.host_readonly_prerequisites()
        self.assertEqual(result["reason"], "LOCAL_READ_ONLY_DIAGNOSTIC_UNAVAILABLE")
        self.assertEqual(result["decision"], "HOLD")
        self.assertNotIn("sensitive account name", json.dumps(result))

    def test_host_readonly_cli_requires_no_bundle_and_exits_nonzero(self):
        with patch.object(preflight, "host_readonly_prerequisites",
                          return_value={"decision": "HOLD", "runtime_authorized": False}) as inspect:
            with redirect_stdout(io.StringIO()) as stdout:
                code = preflight.main(["--host-readonly"])
        inspect.assert_called_once_with()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["decision"], "HOLD")



class InstallationInventoryTests(unittest.TestCase):
    def test_directory_status_exercises_read_access(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root).resolve()
            file = base / "file"
            file.write_text("test", encoding="ascii")
            self.assertEqual(preflight._directory_state(base), "READABLE_UNATTESTED")
            self.assertEqual(preflight._directory_state(file), "WRONG_TYPE")
            self.assertEqual(preflight._directory_state(base / "missing"), "NOT_FOUND")
            with patch.object(preflight.os, "scandir", side_effect=PermissionError):
                self.assertEqual(preflight._directory_state(base), "ACCESS_DENIED")

    def test_opening_paths_and_scm_separately_never_authorizes(self):
        path_type = type(Path())
        with patch.object(preflight.os, "name", "nt"), \
             patch.object(preflight, "Path", path_type), \
             patch.object(preflight, "_directory_state", return_value="ACCESS_DENIED"), \
             patch.object(preflight, "_registry_state", return_value="READABLE_UNATTESTED"), \
             patch.object(preflight, "_scm_states", return_value=(
                 "READABLE_UNATTESTED", dict.fromkeys(preflight.SERVICE_ROLES, "NOT_FOUND"))):
            report = preflight.installation_inventory()
        self.assertEqual(report["services"], dict.fromkeys(preflight.SERVICE_ROLES, "NOT_FOUND"))
        self.assertEqual(report["scm_manager"], "READABLE_UNATTESTED")
        self.assertEqual(report["paths"]["install_parent"], "ACCESS_DENIED")
        self.assertEqual(report["registry"]["base"], "READABLE_UNATTESTED")
        self.assertEqual(report["decision"], "HOLD")
        self.assertFalse(report["runtime_authorized"])

    def test_cli_emits_redacted_held_inventory(self):
        with patch.object(preflight, "installation_inventory", return_value={"decision": "HOLD"}) as inspect:
            with redirect_stdout(io.StringIO()) as stdout:
                status = preflight.main(["--installation-inventory"])
        self.assertEqual(status, 2)
        inspect.assert_called_once_with()
        self.assertEqual(json.loads(stdout.getvalue()), {"decision": "HOLD"})


if __name__ == "__main__":
    unittest.main()
