"""Windows Defender read-only health probe for CodeShield V1.3.

Never changes Defender, Controlled Folder Access, exclusions, service startup,
firewall or Windows policy. Probe output is advisory; no scan is F18 evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess

from .codeshield_contracts import CodeShieldHold

_STATUS_COMMAND = (
    "$ErrorActionPreference='Stop'; "
    "$s=Get-MpComputerStatus -ErrorAction Stop; "
    "[pscustomobject]@{"
    "AntivirusEnabled=$s.AntivirusEnabled;"
    "AMServiceEnabled=$s.AMServiceEnabled;"
    "RealTimeProtectionEnabled=$s.RealTimeProtectionEnabled;"
    "AMRunningMode=[string]$s.AMRunningMode;"
    "AntivirusSignatureAge=$s.AntivirusSignatureAge"
    "} | ConvertTo-Json -Compress -Depth 2"
)
_ALLOWED_MODES = frozenset({"Normal", "Passive Mode", "EDR Block Mode",
                            "SxS Passive Mode", "Not running"})


@dataclass(frozen=True)
class DefenderStatus:
    state: str
    running_mode: str
    signatures_age_days: int | None
    defender_primary_active: bool
    probe_executed: bool
    error_code: str | None = None
    changes_made: bool = False
    can_run_untrusted: bool = False
    f18_independently_verified: bool = False

    def __post_init__(self) -> None:
        if self.state not in {
            "DEFENDER_ACTIVE_READONLY", "HOLD_AV_PASSIVE_OR_STALE",
            "HOLD_AV_UNAVAILABLE", "HOLD_PLATFORM_UNSUPPORTED"
        }:
            raise CodeShieldHold()
        if (self.changes_made is not False or self.can_run_untrusted is not False
            or self.f18_independently_verified is not False):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def _held(code: str, *, executed: bool = False) -> DefenderStatus:
    state = ("HOLD_PLATFORM_UNSUPPORTED" if code == "NOT_WINDOWS"
             else "HOLD_AV_UNAVAILABLE")
    return DefenderStatus(
        state, "UNKNOWN", None, False, executed, error_code=code,
    )


def _trusted_powershell_path() -> Path | None:
    """Locate only the OS System32 PowerShell; PATH lookup is prohibited."""
    if os.name != "nt":
        return None
    root = os.environ.get("SystemRoot", "")
    if (not re.fullmatch(r"[A-Za-z]:\\Windows", root, re.IGNORECASE)
        and not re.fullmatch(r"[A-Za-z]:\\WINNT", root, re.IGNORECASE)):
        return None
    exe = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    try:
        st = exe.stat()
        if not exe.is_file() or st.st_size < 1024:
            return None
    except (OSError, ValueError):
        return None
    return exe


def probe_defender_status(*, timeout_seconds: float = 12.0) -> DefenderStatus:
    """Run a fixed trusted OS read-only query; never accept guest argv/script.

    This probe is intended only for the owner's native Windows protected
    controller context, never the coder guest. Missing native OS = HOLD.
    """
    if (type(timeout_seconds) not in (float, int)
        or not 1 <= timeout_seconds <= 15):
        raise CodeShieldHold()
    exe = _trusted_powershell_path()
    if exe is None:
        return _held("NOT_WINDOWS" if os.name != "nt" else "OS_CLI_UNAVAILABLE")
    root = os.environ["SystemRoot"]
    # No inherited tokens or model-controlled PATH/PSModulePath.
    env = {
        "SystemRoot": root, "WINDIR": root, "ComSpec": str(Path(root) / "System32" / "cmd.exe"),
        "PATH": str(Path(root) / "System32"),
        "PSModulePath": str(Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "Modules"),
    }
    try:
        result = subprocess.run(
            [str(exe), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-Command", _STATUS_COMMAND],
            cwd=str(Path(root) / "System32"),
            env=env, shell=False, capture_output=True, timeout=timeout_seconds,
            check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return _held("PROBE_TIMEOUT_OR_OS_ERROR", executed=True)
    if result.returncode != 0 or len(result.stdout) > 8192:
        return _held("PROBE_EXIT_OR_SIZE", executed=True)
    try:
        obj = json.loads(result.stdout.decode("utf-8-sig"))
        if not isinstance(obj, dict):
            return _held("INVALID_DEFENDER_JSON", executed=True)
        mode = obj.get("AMRunningMode")
        age = obj.get("AntivirusSignatureAge")
        if (mode not in _ALLOWED_MODES or type(age) is not int
            or not 0 <= age <= 36500
            or any(type(obj.get(key)) is not bool for key in (
                "AntivirusEnabled", "AMServiceEnabled", "RealTimeProtectionEnabled",
            ))):
            return _held("INVALID_DEFENDER_FIELDS", executed=True)
        active = (
            mode == "Normal" and obj["AntivirusEnabled"]
            and obj["AMServiceEnabled"] and obj["RealTimeProtectionEnabled"]
            and age <= 7
        )
        return DefenderStatus(
            "DEFENDER_ACTIVE_READONLY" if active else "HOLD_AV_PASSIVE_OR_STALE",
            mode, age, active, True,
        )
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return _held("INVALID_DEFENDER_JSON", executed=True)


@dataclass(frozen=True)
class OptionalDownloadScanIntent:
    """A human-approved scope is still mandatory before any Start-MpScan."""
    file_sha256: str
    scope_ref: str
    state: str = "HOLD_OWNER_SCOPED_SCAN_NOT_IMPLEMENTED"
    scan_started: bool = False
    may_change_defender_settings: bool = False
    may_execute_download: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.file_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", self.file_sha256) is None
            or not isinstance(self.scope_ref, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{3,64}", self.scope_ref) is None
            or self.state != "HOLD_OWNER_SCOPED_SCAN_NOT_IMPLEMENTED"
            or self.scan_started is not False
            or self.may_change_defender_settings is not False
            or self.may_execute_download is not False):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def plan_optional_download_scan(*, file_sha256: str, scope_ref: str) -> OptionalDownloadScanIntent:
    """Prepare a data-only request; actual scan requires protected owner GO."""
    return OptionalDownloadScanIntent(file_sha256, scope_ref)
