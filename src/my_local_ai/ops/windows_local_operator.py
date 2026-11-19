"""Bounded read-only Windows diagnostics for owner-pasted instructions.

ChatGPT text is untrusted: no arbitrary shell, paths, network, writes,
privilege changes, approvals, generated code or model-driven dispatch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess

_SCHEMA = "mla-local-operator/v1"
_ACTIONS = frozenset({"windows-preflight", "tpm-status", "defender-status",
                      "protected-path-presence", "cng-provider-status"})
_ALIASES = {
    "MLA 보안 환경 진단": "windows-preflight",
    "Windows 보안 환경 진단": "windows-preflight",
    "TPM 상태 확인": "tpm-status",
    "Defender 상태 확인": "defender-status",
    "MLA 보호 폴더 확인": "protected-path-presence",
    "CNG 서명 공급자 확인": "cng-provider-status",
}
_TPM_QUERY = ("$ErrorActionPreference='Stop'; $t=Get-Tpm -ErrorAction Stop; "
              "[pscustomobject]@{TpmPresent=[bool]$t.TpmPresent;"
              "TpmReady=[bool]$t.TpmReady;TpmEnabled=[bool]$t.TpmEnabled}"
              " | ConvertTo-Json -Compress")
_PROTECTED = Path(r"C:\ProgramData\MyLocalAI\Protected\v1")


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate operator key")
        obj[key] = value
    return obj


def parse_operator_request(raw: str) -> str:
    """Exact aliases or strict versioned JSON; no fuzzy command translation."""
    if type(raw) is not str or not 1 <= len(raw) <= 1024 or raw != raw.strip():
        raise ValueError("invalid operator request")
    if raw in _ALIASES:
        return _ALIASES[raw]
    try:
        obj = json.loads(raw, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constant")))
    except (json.JSONDecodeError, ValueError, TypeError):
        raise ValueError("unknown operator request") from None
    if (type(obj) is not dict or set(obj) != {"schema", "action"}
        or obj["schema"] != _SCHEMA or type(obj["action"]) is not str
        or obj["action"] not in _ACTIONS):
        raise ValueError("unsupported operator action")
    return obj["action"]


def operator_catalog() -> dict:
    return {"schema": _SCHEMA, "allowed_actions": sorted(_ACTIONS),
            "example_request": "MLA 보안 환경 진단", "read_only": True,
            "arbitrary_shell_allowed": False, "owner_os_changes_allowed": False,
            "external_network_allowed": False, "p2": "LOCKED",
            "formal_verified_rate": "UNASSESSED"}


def _tpm_status() -> dict:
    from my_local_ai.security.defender_status import _trusted_powershell_path
    exe = _trusted_powershell_path()
    if exe is None:
        return {"state": "HOLD_OS_CLI_UNAVAILABLE", "probe_executed": False}
    root = os.environ["SystemRoot"]
    env = {"SystemRoot": root, "WINDIR": root,
           "ComSpec": str(Path(root) / "System32" / "cmd.exe"),
           "PATH": str(Path(root) / "System32"),
           "PSModulePath": str(Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "Modules")}
    try:
        run = subprocess.run(
            [str(exe), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _TPM_QUERY],
            cwd=str(Path(root) / "System32"), env=env, shell=False,
            capture_output=True, check=False, timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if run.returncode != 0 or len(run.stdout) > 2048:
            return {"state": "HOLD_QUERY_FAILED", "probe_executed": True}
        obj = json.loads(run.stdout.decode("utf-8-sig"), object_pairs_hook=_unique_pairs)
        fields = ("TpmPresent", "TpmReady", "TpmEnabled")
        if (type(obj) is not dict or set(obj) != set(fields)
            or any(type(obj[k]) is not bool for k in fields)):
            raise ValueError("invalid TPM fields")
        return {"state": "READ_ONLY_RESULT", "probe_executed": True,
                "tpm_present": obj["TpmPresent"], "tpm_ready": obj["TpmReady"],
                "tpm_enabled": obj["TpmEnabled"]}
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError, TypeError, KeyError):
        return {"state": "HOLD_QUERY_FAILED", "probe_executed": True}


def _defender_status() -> dict:
    from my_local_ai.security.defender_status import probe_defender_status
    result = probe_defender_status()
    return {"state": result.state, "probe_executed": result.probe_executed,
            "primary_active": result.defender_primary_active,
            "signature_age_days": result.signatures_age_days,
            "mode": result.running_mode, "error_code": result.error_code}


def _protected_path_status() -> dict:
    try:
        info = _PROTECTED.lstat()
        if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0)
               & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return {"state": "HOLD_UNSAFE_ALIAS", "probe_executed": True}
        return {"state": "PRESENT_UNVERIFIED" if stat.S_ISDIR(info.st_mode)
                else "HOLD_NOT_DIRECTORY", "probe_executed": True}
    except FileNotFoundError:
        return {"state": "NOT_PRESENT", "probe_executed": True}
    except (OSError, ValueError):
        return {"state": "HOLD_PATH_UNAVAILABLE", "probe_executed": True}



def _cng_provider_status() -> dict:
    """Native read-only software KSP presence and existing HKLM selection.

    Opens only a fixed provider handle and its documented implementation
    property. It never opens/creates/imports/deletes/signs with any key, and
    it never treats KSP presence or a registry string as protected trust.
    """
    import ctypes as c
    from ctypes import wintypes as w
    import winreg

    # No request can influence the KSP name or registry location.
    pin_mode = "NOT_CONFIGURED"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\MyLocalAI\ProtectedBrokers\v1", 0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            try:
                value, kind = winreg.QueryValueEx(key, "KeyProviderMode")
            except FileNotFoundError:
                pin_mode = "TPM_V1_LEGACY"
            else:
                if kind != winreg.REG_SZ or type(value) is not str or value not in {
                    "TPM_V1", "SOFTWARE_CNG_OWNER_APPROVED_V1"
                }:
                    return {"state": "HOLD_PIN_INVALID", "probe_executed": True,
                            "profile": "INVALID", "protected_trust_verified": False,
                            "key_provisioned_verified": False}
                pin_mode = value
    except FileNotFoundError:
        pass  # An unprovisioned PC is expected, never an implicit software GO.
    except OSError:
        return {"state": "HOLD_PIN_UNREADABLE", "probe_executed": True,
                "profile": "UNREADABLE", "protected_trust_verified": False,
                "key_provisioned_verified": False}

    provider = c.c_size_t()
    try:
        dll = c.WinDLL("ncrypt.dll", use_last_error=True, winmode=0x800)
        open_provider = dll.NCryptOpenStorageProvider
        open_provider.argtypes = [c.POINTER(c.c_size_t), w.LPCWSTR, w.DWORD]
        open_provider.restype = c.c_long
        get_property = dll.NCryptGetProperty
        get_property.argtypes = [c.c_size_t, w.LPCWSTR, c.c_void_p, w.DWORD,
                                 c.POINTER(w.DWORD), w.DWORD]
        get_property.restype = c.c_long
        free = dll.NCryptFreeObject
        free.argtypes = [c.c_size_t]
        free.restype = c.c_long
        if open_provider(c.byref(provider),
                         "Microsoft Software Key Storage Provider", 0) != 0:
            return {"state": "HOLD_KSP_UNAVAILABLE", "probe_executed": True,
                    "profile": pin_mode, "protected_trust_verified": False,
                    "key_provisioned_verified": False}
        flags, length = w.DWORD(), w.DWORD()
        ok = get_property(provider.value, "Impl Type", c.byref(flags),
                          c.sizeof(flags), c.byref(length), 0x40)
        if (ok != 0 or length.value != 4 or not flags.value & 0x2
            or flags.value & (0x1 | 0x8)):
            return {"state": "HOLD_KSP_CAPABILITY", "probe_executed": True,
                    "profile": pin_mode, "protected_trust_verified": False,
                    "key_provisioned_verified": False}
        return {"state": "READ_ONLY_RESULT", "probe_executed": True,
                "software_ksp_available": True, "profile": pin_mode,
                "profile_enabled": pin_mode == "SOFTWARE_CNG_OWNER_APPROVED_V1",
                "protected_trust_verified": False, "key_provisioned_verified": False,
                "runtime_authorized": False}
    except (OSError, ValueError, TypeError, AttributeError):
        return {"state": "HOLD_KSP_UNAVAILABLE", "probe_executed": False,
                "profile": pin_mode, "protected_trust_verified": False,
                "key_provisioned_verified": False}
    finally:
        if provider.value:
            free(provider.value)


def run_operator_request(raw: str) -> dict:
    """Only fixed diagnostic functions under the current OS account."""
    action = parse_operator_request(raw)
    result = {"schema": _SCHEMA, "action": action, "state": "HOLD",
              "read_only": True, "owner_approval_verified": False,
              "arbitrary_shell_executed": False, "os_settings_changed": False,
              "network_requested": False, "execution_authority_granted": False,
              "p2": "LOCKED", "formal_verified_rate": "UNASSESSED"}
    if os.name != "nt":
        return {**result, "reason": "WINDOWS_REQUIRED", "checks": {}}
    mapping = {"tpm-status": _tpm_status, "defender-status": _defender_status,
               "protected-path-presence": _protected_path_status,
               "cng-provider-status": _cng_provider_status}
    selected = tuple(mapping) if action == "windows-preflight" else (action,)
    checks = {}
    for key in selected:
        try:
            checks[key] = mapping[key]()
        except (OSError, ValueError, TypeError, KeyError):
            checks[key] = {"state": "HOLD_CHECK_FAILED", "probe_executed": False}
    good = {"READ_ONLY_RESULT", "DEFENDER_ACTIVE_READONLY",
            "HOLD_AV_PASSIVE_OR_STALE", "NOT_PRESENT", "PRESENT_UNVERIFIED"}
    return {**result, "state": "READ_ONLY_RESULT" if all(
        check["state"] in good for check in checks.values())
        else "HOLD_PARTIAL", "checks": checks}
