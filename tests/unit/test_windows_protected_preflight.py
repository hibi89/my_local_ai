"""Synthetic safety tests for staged Windows images, with no native OS writes."""
from pathlib import Path
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

    def test_modified_installed_executable_is_rejected(self):
        name = preflight.IMAGE_BY_ROLE["owner"]
        with (self.installed / name / (name + ".exe")).open("ab") as stream:
            stream.write(b"tamper")
        self.assertEqual(self.check()["code"], "STAGED_INSTALLED_HASH_MISMATCH")

    def test_modified_installed_dependency_is_rejected(self):
        name = preflight.IMAGE_BY_ROLE["reviewer"]
        (self.installed / name / "_internal" / "data.bin").write_bytes(b"tamper")
        self.assertEqual(self.check()["code"], "STAGED_INSTALLED_HASH_MISMATCH")

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


if __name__ == "__main__":
    unittest.main()
