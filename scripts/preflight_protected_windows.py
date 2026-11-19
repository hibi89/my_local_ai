"""Read-only Windows preflight for staged versus installed MLA protected images.

Does not create accounts, keys, registry values, ACLs, services or approvals.
A matching result is NEVER a trust attestation or permission to run MLA.
This executable does not launch any of the frozen images.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

from build_protected_windows import IMAGES, PYINSTALLER_VERSION, _hash_file, inspect_image

BASE = r"SOFTWARE\MyLocalAI\ProtectedBrokers\v1"
SID = re.compile(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
KEY = re.compile(r"MyLocalAI\.[A-Za-z0-9_.-]{3,64}\Z")
IMAGE_BY_ROLE = {role: name for role, name, _ in IMAGES}
SERVICE_ROLES = ("owner", "reviewer", "scanner")
MAX_MANIFEST_BYTES = 1024 * 1024
REPARSE = 0x400


class PreflightHold(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _no_links(path: Path) -> None:
    """Reject links/junctions in the path's observed ancestry."""
    for node in (path, *path.parents):
        info = node.lstat()
        if node.is_symlink() or getattr(info, "st_file_attributes", 0) & REPARSE:
            raise PreflightHold("REPARSE_PATH_HOLD")


def _exact_json(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PreflightHold("DUPLICATE_MANIFEST_KEY")
            result[key] = value
        return result
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightHold("INVALID_MANIFEST") from exc
    if type(obj) is not dict:
        raise PreflightHold("INVALID_MANIFEST")
    return obj


def _inventory(root: Path, *, expected_names: set[str], with_manifest: bool) -> dict:
    _no_links(root)
    if not root.is_dir():
        raise PreflightHold("MISSING_IMAGE_ROOT")
    permitted = set(expected_names)
    if with_manifest:
        permitted.add("UNTRUSTED_BUILD_MANIFEST.json")
    if {child.name for child in root.iterdir()} != permitted:
        raise PreflightHold("UNEXPECTED_IMAGE_ROOT_CONTENTS")
    observations = {}
    for _, name, _ in IMAGES:
        folder = root / name
        _no_links(folder)
        try:
            observations[name] = inspect_image(folder, name)
        except (ValueError, OSError) as exc:
            raise PreflightHold("INVALID_FROZEN_IMAGE") from exc
    return observations


def verify_stage_and_install(bundle: Path, installed: Path) -> tuple[dict, dict]:
    """Verify every byte against untrusted build inventory and installed copy."""
    if not bundle.is_absolute() or not installed.is_absolute():
        raise PreflightHold("ABSOLUTE_PATH_REQUIRED")
    if (bundle == installed or bundle in installed.parents
            or installed in bundle.parents):
        raise PreflightHold("STAGE_INSTALL_NOT_SEPARATE")
    marker = bundle / "UNTRUSTED_BUILD_MANIFEST.json"
    _no_links(marker)
    if not marker.is_file() or not 1 <= marker.stat().st_size <= MAX_MANIFEST_BYTES:
        raise PreflightHold("MISSING_MANIFEST")
    data = marker.read_bytes()
    if len(data) > MAX_MANIFEST_BYTES:
        raise PreflightHold("INVALID_MANIFEST")
    manifest = _exact_json(data)
    if (set(manifest) != {
        "schema", "trusted_or_installed", "os_accounts_keys_acl_service_changes",
        "windows_native_acceptance", "python", "pyinstaller", "images",
    } or manifest["schema"] != "mla-protected-bundle-inventory/v1"
        or manifest["trusted_or_installed"] is not False
        or manifest["os_accounts_keys_acl_service_changes"] != "NOT_PERFORMED"
        or manifest["windows_native_acceptance"] != "NOT_RUN"
        or manifest["python"] != "3.11" or manifest["pyinstaller"] != PYINSTALLER_VERSION
        or type(manifest["images"]) is not dict
        or set(manifest["images"]) != set(IMAGE_BY_ROLE)):
        raise PreflightHold("INVALID_MANIFEST")
    names = set(IMAGE_BY_ROLE.values())
    stage = _inventory(bundle, expected_names=names, with_manifest=True)
    destination = _inventory(installed, expected_names=names, with_manifest=False)
    for role, name, kind in IMAGES:
        expected = {
            "directory": name, "executable": name + ".exe",
            "scm_service": "MyLocalAI." + role + ".v1" if kind == "service" else None,
            **stage[name],
        }
        if manifest["images"][role] != expected or destination[name] != stage[name]:
            raise PreflightHold("STAGED_INSTALLED_HASH_MISMATCH")
    return manifest, destination


def _native_settings() -> dict:
    """Read 64-bit HKLM and registered service config. No writes or key opens."""
    if os.name != "nt":
        raise PreflightHold("WINDOWS_ONLY")
    import winreg

    def read(path, name, kind):
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as handle:
            value, observed = winreg.QueryValueEx(handle, name)
        if observed != kind:
            raise PreflightHold("REGISTRY_PIN_TYPE_MISMATCH")
        return value

    base = BASE
    settings = {
        "controller_sid": read(base, "ControllerSid", winreg.REG_SZ),
        "owner_sid": read(base, "InteractiveOwnerSid", winreg.REG_SZ),
        "owner_session": read(base, "OwnerSessionId", winreg.REG_DWORD),
        "owner_ui_sha": read(base, "OwnerUiImageSha256", winreg.REG_SZ),
        "owner_ui_key": read(base, "OwnerUiKeyName", winreg.REG_SZ),
        "owner_ui_public": read(base, "OwnerUiPublicKeyBlob", winreg.REG_BINARY),
        "roles": {},
    }
    try:
        settings["key_provider_mode"] = read(base, "KeyProviderMode", winreg.REG_SZ)
    except FileNotFoundError:
        settings["key_provider_mode"] = "TPM_V1"  # Legacy TPM-only, no auto fallback.
    for role in SERVICE_ROLES:
        prefix = base + "\\" + role
        service = r"SYSTEM\CurrentControlSet\Services\MyLocalAI." + role + ".v1"
        settings["roles"][role] = {
            "sid": read(prefix, "PrincipalSid", winreg.REG_SZ),
            "sha": read(prefix, "ImageSha256", winreg.REG_SZ),
            "key": read(prefix, "KeyName", winreg.REG_SZ),
            "public": read(prefix, "PublicKeyBlob", winreg.REG_BINARY),
            "image_path": read(service, "ImagePath", winreg.REG_SZ),
            "service_type": read(service, "Type", winreg.REG_DWORD),
            "start": read(service, "Start", winreg.REG_DWORD),
        }
    return settings


def _valid_public(blob: object) -> bool:
    return type(blob) is bytes and len(blob) == 72 and blob[:8] == b"ECS1\x20\x00\x00\x00"


def verify_pins(pins: dict, destination: dict, installed: Path) -> None:
    """Check read-only configuration equality, never use pins as runtime GO."""
    if type(pins) is not dict or type(pins.get("roles")) is not dict:
        raise PreflightHold("REGISTRY_PINS_INVALID")
    roles = pins["roles"]
    profile = pins.get("key_provider_mode", "TPM_V1")
    if (type(profile) is not str or profile not in (
            "TPM_V1", "SOFTWARE_CNG_OWNER_APPROVED_V1")):
        raise PreflightHold("CNG_PROVIDER_PIN_INVALID")
    if set(roles) != set(SERVICE_ROLES):
        raise PreflightHold("REGISTRY_PINS_INVALID")
    sids = [pins.get("controller_sid"), pins.get("owner_sid")]
    keys = [pins.get("owner_ui_key")]
    blobs = [pins.get("owner_ui_public")]
    image_shas = [pins.get("owner_ui_sha")]
    if (type(pins.get("owner_session")) is not int
        or not 1 <= pins["owner_session"] < 65536):
        raise PreflightHold("OWNER_SESSION_PIN_INVALID")
    for role in SERVICE_ROLES:
        entry = roles[role]
        if type(entry) is not dict:
            raise PreflightHold("REGISTRY_PINS_INVALID")
        sids.append(entry.get("sid"))
        keys.append(entry.get("key"))
        blobs.append(entry.get("public"))
        image_shas.append(entry.get("sha"))
        if (type(entry.get("service_type")) is not int
            or entry["service_type"] != 0x10
            or type(entry.get("start")) is not int
            or entry["start"] not in (3, 4)):
            raise PreflightHold("SERVICE_CONFIG_INVALID")
        exe = installed / IMAGE_BY_ROLE[role] / (IMAGE_BY_ROLE[role] + ".exe")
        path = entry.get("image_path")
        if type(path) is not str or path not in (str(exe), '"' + str(exe) + '"'):
            raise PreflightHold("SCM_IMAGE_PATH_MISMATCH")
        if entry.get("sha") != destination[IMAGE_BY_ROLE[role]]["image_sha256"]:
            raise PreflightHold("SERVICE_IMAGE_PIN_MISMATCH")
    if (any(type(s) is not str or SID.fullmatch(s) is None for s in sids)
        or len(set(sids)) != 5
        or any(type(k) is not str or KEY.fullmatch(k) is None for k in keys)
        or len(set(keys)) != 4
        or any(not _valid_public(blob) for blob in blobs)
        or len(set(blobs)) != 4
        or any(type(d) is not str or SHA.fullmatch(d) is None for d in image_shas)
        or len(set(image_shas)) != 4):
        raise PreflightHold("PRINCIPALS_OR_KEYS_NOT_INDEPENDENT")
    if pins["owner_ui_sha"] != destination[IMAGE_BY_ROLE["owner-ui"]]["image_sha256"]:
        raise PreflightHold("OWNER_IMAGE_PIN_MISMATCH")


def preflight(bundle: Path, installed: Path, *, settings: dict | None = None) -> dict:
    """Result is always HOLD, including when static hashes/config match."""
    result = {
        "schema": "mla-protected-readonly-preflight/v1",
        "decision": "HOLD",
        "precheck": "BLOCKED",
        "code": "PRECHECK_NOT_RUN",
        "os_modified": False,
        "runtime_authorized": False,
        "owner_signature_verified": False,
        "independent_f18_verified": False,
        "defender_scan_verified": False,
        "required_field_checks": [
            "ACTUAL_SCMSERVICE_PRINCIPAL_AND_RUNNING_IMAGE",
            "ACL_ANCESTRY_AND_PINNED_CNG_NONEXPORT_POLICY_KEY_USAGE",
            "SEPARATE_INTERACTIVE_OWNER_SESSION_SIGNED_E2E",
            "INDEPENDENT_F18_RUNTIME_AND_REQ14_ACCEPTANCE",
            "OWNER_APPROVED_WINDOWS_DEFENDER_SCAN",
        ],
    }
    try:
        manifest, destination = verify_stage_and_install(bundle, installed)
        if settings is None:
            settings = _native_settings()
        verify_pins(settings, destination, installed)
        result["precheck"] = "MATCHED_UNATTESTED"
        result["code"] = "PIN_AND_IMAGE_MATCH_NOT_RUNTIME_TRUST"
        result["cng_provider_mode"] = settings.get("key_provider_mode", "TPM_V1")
        result["cng_hardware_attested"] = False
        result["image_sha256"] = {
            role: destination[name]["image_sha256"]
            for role, name, _ in IMAGES
        }
    except (PreflightHold, OSError, ValueError, KeyError, TypeError) as exc:
        result["code"] = exc.code if isinstance(exc, PreflightHold) else "READ_ONLY_PRECHECK_ERROR"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True,
                        help="Absolute folder with the original untrusted build manifest")
    parser.add_argument("--installed-root", type=Path, required=True,
                        help="Absolute existing protected installation root (read only)")
    args = parser.parse_args(argv)
    result = preflight(args.bundle, args.installed_root)
    print(json.dumps(result, sort_keys=True, indent=2))
    # Even a perfect image/HKLM comparison never authorizes a protected action.
    # A non-zero exit prevents CI/install wrappers from treating this as GO.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
