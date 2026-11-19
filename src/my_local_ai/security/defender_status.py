"""Windows Defender health/client and protected custom-file scan server.

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

from my_local_ai.security.codeshield_contracts import CodeShieldHold

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


# CS-SWU-012: create a *non-executing* owner-action request. The Controller
# cannot authenticate an owner grant or F18 with user/model-supplied booleans.
from hashlib import sha256 as _sha256
import stat as _stat

from my_local_ai.security.codeshield_contracts import (
    CodeShieldContext, checked_relative_path,
)
from my_local_ai.security.ast_preflight import preflight_changed_paths

_MAX_OWNER_SCAN_BYTES = 64 * 1024 * 1024
_ALLOWED_SCAN_EXTENSIONS = frozenset({
    ".exe", ".dll", ".msi", ".zip", ".ps1", ".js", ".py",
})


@dataclass(frozen=True)
class DefenderOwnerScanRequest:
    """Replay-bound data-only intent; NEVER a grant to call Start-MpScan.

    Plan/source/nonce/lease are proposal metadata, not protected signatures.
    A future Windows broker must rederive them from its own trusted ledger.
    """
    context_sha256: str
    candidate_git_sha: str
    consent_reference: str
    relative_target_sha256: str
    content_sha256: str
    content_size: int
    plan_sha256: str
    source_git_sha: str
    nonce_sha256: str
    lease_epoch: int
    stage: str = "HOLD_OWNER_ACTION_AND_TRUSTED_BROKER_NOT_AVAILABLE"
    owner_grant_verified: bool = False
    os_identity_verified: bool = False
    scan_started: bool = False
    defender_policy_modified: bool = False
    f18_verified: bool = False
    execute_download_allowed: bool = False

    def __post_init__(self) -> None:
        for digest in (
            self.context_sha256, self.relative_target_sha256,
            self.content_sha256, self.plan_sha256, self.nonce_sha256,
        ):
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise CodeShieldHold("UNTRUSTED_DECISION")
        if (not isinstance(self.candidate_git_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", self.candidate_git_sha) is None
            or not isinstance(self.source_git_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", self.source_git_sha) is None
            or type(self.lease_epoch) is not int
            or not 1 <= self.lease_epoch <= 2**63 - 1
            or not isinstance(self.consent_reference, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}",
                                self.consent_reference)
            or type(self.content_size) is not int
            or not 1 <= self.content_size <= _MAX_OWNER_SCAN_BYTES
            or self.stage != "HOLD_OWNER_ACTION_AND_TRUSTED_BROKER_NOT_AVAILABLE"
            or any(getattr(self, name) is not False for name in (
                "owner_grant_verified", "os_identity_verified",
                "scan_started", "defender_policy_modified", "f18_verified",
                "execute_download_allowed",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "context_sha256": self.context_sha256,
            "candidate_git_sha": self.candidate_git_sha,
            "relative_target_sha256": self.relative_target_sha256,
            "content_sha256": self.content_sha256,
            "content_size": self.content_size,
            "owner_grant_verified": False,
            "independent_f18": False,
            "scan_started": False,
            "defender_policy_modified": False,
            "execution_allowed": False,
        }


def _read_bounded_untrusted_scan_target(path: Path) -> tuple[str, int]:
    """Read only regular non-link bytes; re-check ancestry and inode/size/mtime."""
    try:
        for segment in (path, *path.parents):
            info = segment.lstat()
            if (_stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0)
                   & getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise CodeShieldHold("UNSAFE_PATH")
        before = path.lstat()
        if (not _stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 1 <= before.st_size <= _MAX_OWNER_SCAN_BYTES):
            raise CodeShieldHold("UNSAFE_PATH")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        digest = _sha256()
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            identity = (before.st_dev, before.st_ino, before.st_size,
                        before.st_mtime_ns)
            if ((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                != identity):
                raise CodeShieldHold("STALE_EVIDENCE")
            size = 0
            while size <= _MAX_OWNER_SCAN_BYTES:
                chunk = stream.read(min(65536, _MAX_OWNER_SCAN_BYTES - size + 1))
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
            endfd = os.fstat(stream.fileno())
        after = path.lstat()
        if (size != before.st_size
            or (endfd.st_dev, endfd.st_ino, endfd.st_size, endfd.st_mtime_ns)
               != identity
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
               != identity):
            raise CodeShieldHold("STALE_EVIDENCE")
        return digest.hexdigest(), size
    except CodeShieldHold:
        raise
    except (OSError, OverflowError, ValueError):
        raise CodeShieldHold("UNSAFE_PATH") from None


def preview_owner_scoped_defender_scan(
    context: CodeShieldContext, *,
    disposable_worktree: str | Path,
    original_checkout: str | Path,
    target_relative_path: str,
    expected_content_sha256: str,
) -> DefenderOwnerScanRequest:
    """Prepare a read-only scoped Defender scan request, not a scan or OS GO.

    The caller's consent *reference* is not verified owner consent. An
    independently protected Windows broker must validate the signer, lease,
    scope, file identity and issue a separate action-bound grant later.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    relative = checked_relative_path(target_relative_path)
    if (relative not in context.allowed_paths
        or Path(relative).suffix.casefold() not in _ALLOWED_SCAN_EXTENSIONS
        or not isinstance(expected_content_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_content_sha256) is None):
        raise CodeShieldHold("UNSAFE_PATH")
    scope = preflight_changed_paths(
        context, worktree=disposable_worktree,
        original_checkout=original_checkout,
        changed_paths=(relative,),
    )
    if scope.may_write or scope.may_execute or scope.git_diff_verified:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    root = Path(disposable_worktree)
    if not root.is_absolute():
        raise CodeShieldHold("UNSAFE_PATH")
    actual, size = _read_bounded_untrusted_scan_target(root / relative)
    if actual != expected_content_sha256:
        raise CodeShieldHold("STALE_EVIDENCE")
    return DefenderOwnerScanRequest(
        context.fingerprint_sha256, context.candidate_git_sha,
        context.owner_consent_ref, _sha256(relative.encode("utf-8")).hexdigest(),
        actual, size,
        context.plan_sha256, context.source_git_sha,
        context.nonce_sha256, context.lease_epoch,
    )


@dataclass(frozen=True)
class DefenderFileScanResult:
    state: str
    content_sha256: str
    scan_completed: bool
    finding_count: int | None
    reason: str
    scan_reference: str | None = None
    scan_error_code: str | None = None
    defender_policy_modified: bool = False
    execution_allowed: bool = False
    f18_verified: bool = False
    may_promote: bool = False

    def __post_init__(self):
        states = {"COMPLETED_CLEAN", "MALWARE_DETECTED_HOLD", "SCAN_ERROR_HOLD", "UNKNOWN_HOLD",
                  "SCAN_TIMEOUT_HOLD", "NOT_RUN_HOLD", "RESULT_REJECTED_HOLD"}
        if (self.state not in states
            or type(self.content_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) is None
            or type(self.scan_completed) is not bool
            or self.state == "COMPLETED_CLEAN" and (not self.scan_completed
                or type(self.finding_count) is not int or self.finding_count != 0)
            or self.state == "MALWARE_DETECTED_HOLD" and (not self.scan_completed
                or type(self.finding_count) is not int or self.finding_count <= 0)
            or self.state in {"SCAN_ERROR_HOLD", "SCAN_TIMEOUT_HOLD", "UNKNOWN_HOLD",
                              "NOT_RUN_HOLD", "RESULT_REJECTED_HOLD"}
                and (self.scan_completed or self.finding_count is not None)
            or self.scan_reference is not None
                and (not isinstance(self.scan_reference, str)
                     or re.fullmatch(r"[A-Za-z0-9_-]{8,96}", self.scan_reference) is None)
            or self.scan_error_code is not None
                and (not isinstance(self.scan_error_code, str)
                     or re.fullmatch(r"[A-Z0-9_]{3,64}", self.scan_error_code) is None)
            or self.state == "COMPLETED_CLEAN"
                and (self.scan_reference is None or self.scan_error_code is not None)
            or self.state == "MALWARE_DETECTED_HOLD"
                and (self.scan_reference is None or self.scan_error_code is not None)
            or self.state in {"SCAN_ERROR_HOLD", "SCAN_TIMEOUT_HOLD"}
                and (self.scan_reference is None or self.scan_error_code is None)
            or self.state == "UNKNOWN_HOLD" and self.scan_error_code is None
            or any(getattr(self, field) is not False for field in (
                "defender_policy_modified", "execution_allowed", "f18_verified", "may_promote"))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


_DEFENDER_RESULT_FIELDS = frozenset({
    "outcome", "content_sha256", "content_size", "scan_completed",
    "timed_out", "finding_count", "engine_exit_code", "scan_error_code",
    "detection_evidence_sha256", "remediation", "policy_changed",
    "scan_reference",
})


def _classify_protected_defender_result(
    result: object, request: DefenderOwnerScanRequest,
) -> DefenderFileScanResult:
    """Validate the broker-signed engine outcome without trusting exit code alone.

    Microsoft documents exit code 2 as either an unremediated detection or a
    scan error. A detection therefore needs separate hashed evidence; ambiguous
    output is an error/HOLD, never reported as clean or malware by inference.
    """
    def rejected(code: str = "DEFENDER_RESULT_REJECTED"):
        return DefenderFileScanResult(
            "RESULT_REJECTED_HOLD", request.content_sha256, False, None, code,
        )

    if type(result) is not dict or set(result) != _DEFENDER_RESULT_FIELDS:
        return rejected()
    if (result["content_sha256"] != request.content_sha256
        or type(result["content_size"]) is not int
        or result["content_size"] != request.content_size
        or result["remediation"] != "DISABLED"
        or result["policy_changed"] is not False
        or not isinstance(result["scan_reference"], str)
        or re.fullmatch(r"[A-Za-z0-9_-]{8,96}", result["scan_reference"]) is None):
        return rejected()

    outcome = result["outcome"]
    completed = result["scan_completed"]
    timed_out = result["timed_out"]
    count = result["finding_count"]
    exit_code = result["engine_exit_code"]
    error_code = result["scan_error_code"]
    evidence = result["detection_evidence_sha256"]
    if type(completed) is not bool or type(timed_out) is not bool:
        return rejected()
    if outcome == "COMPLETED_CLEAN":
        if (completed is not True or timed_out is not False
            or type(count) is not int or count != 0 or type(exit_code) is not int
            or exit_code != 0 or error_code is not None or evidence is not None):
            return rejected()
        return DefenderFileScanResult(
            "COMPLETED_CLEAN", request.content_sha256, True, 0,
            "DEFENDER_COMPLETED_NO_FINDINGS", result["scan_reference"],
        )
    if outcome == "MALWARE_DETECTED":
        if (completed is not True or timed_out is not False
            or type(count) is not int or not 1 <= count <= 100000
            or type(exit_code) is not int or exit_code != 2
            or error_code is not None or not isinstance(evidence, str)
            or re.fullmatch(r"[0-9a-f]{64}", evidence) is None):
            return rejected()
        return DefenderFileScanResult(
            "MALWARE_DETECTED_HOLD", request.content_sha256, True, count,
            "DEFENDER_DETECTION_EVIDENCE_PRESENT", result["scan_reference"],
        )
    if outcome in {"SCAN_ERROR", "UNKNOWN"}:
        if (completed is not False or timed_out is not False or count is not None
            or type(exit_code) is not int or outcome == "SCAN_ERROR" and exit_code == 0
            or not isinstance(error_code, str)
            or re.fullmatch(r"[A-Z0-9_]{3,64}", error_code) is None
            or evidence is not None):
            return rejected()
        return DefenderFileScanResult(
            "UNKNOWN_HOLD" if outcome == "UNKNOWN" else "SCAN_ERROR_HOLD",
            request.content_sha256, False, None,
            "DEFENDER_RESULT_UNKNOWN" if outcome == "UNKNOWN" else "DEFENDER_SCAN_ERROR",
            result["scan_reference"], error_code,
        )
    if outcome == "TIMEOUT":
        if (completed is not False or timed_out is not True or count is not None
            or exit_code is not None or error_code != "SCAN_TIMEOUT"
            or evidence is not None):
            return rejected()
        return DefenderFileScanResult(
            "SCAN_TIMEOUT_HOLD", request.content_sha256, False, None,
            "DEFENDER_SCAN_TIMEOUT", result["scan_reference"], "SCAN_TIMEOUT",
        )
    return rejected()


def run_owner_scoped_defender_scan(
    context: CodeShieldContext, *, disposable_worktree: str | Path,
    original_checkout: str | Path, target_relative_path: str,
    expected_content_sha256: str, timeout_seconds: int = 60,
) -> DefenderFileScanResult:
    """Scoped owner action -> protected scanner -> exact file scan result.

    The native service must copy the locked, rehashed file into its private
    no-egress scan area and use pinned MpCmdRun custom-file scan with
    DisableRemediation. Start-MpScan's implicit remediation must NOT be used.
    It must distinguish detection, scan errors and cancellation; a request ID
    or a successful command submission alone is never a completed clean scan.
    No executable, policy, exclusion, CFA or remediation is run by this client.
    """
    from .codeshield_contracts import DataClass
    from my_local_ai.state.consent import ProtectedBrokerHold, dispatch_protected_action
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise CodeShieldHold()
    request = preview_owner_scoped_defender_scan(
        context, disposable_worktree=disposable_worktree, original_checkout=original_checkout,
        target_relative_path=target_relative_path, expected_content_sha256=expected_content_sha256)
    def held(state, reason):
        return DefenderFileScanResult(state, request.content_sha256, False, None, reason)
    if os.name != "nt":
        return held("NOT_RUN_HOLD", "WINDOWS_REQUIRED")
    if context.data_class != DataClass.PUBLIC_SYNTHETIC:
        return held("NOT_RUN_HOLD", "PROTECTED_DATA_SCOPE_HOLD")
    try:
        reply = dispatch_protected_action("scanner", "defender", binding={
            "task_id": context.task_id, "run_id": context.run_id,
            "plan_sha256": request.plan_sha256, "source_sha": request.source_git_sha,
            "candidate_sha": request.candidate_git_sha, "lease_epoch": request.lease_epoch,
            "nonce_sha256": request.nonce_sha256, "owner_consent_ref": request.consent_reference,
        }, payload={"context_sha256": request.context_sha256,
            "disposable_root": str(Path(disposable_worktree)),
            "relative_target": target_relative_path, "content_sha256": request.content_sha256,
            "content_size": request.content_size, "timeout_seconds": timeout_seconds,
            "policy": "DEFENDER_CUSTOM_FILE_OFFLINE_DISABLE_REMEDIATION_V1"},
            timeout_seconds=timeout_seconds + 5)
        # Repeat scope, ancestry, content and candidate binding after scanning.
        after = preview_owner_scoped_defender_scan(
            context, disposable_worktree=disposable_worktree, original_checkout=original_checkout,
            target_relative_path=target_relative_path, expected_content_sha256=expected_content_sha256)
        if after != request:
            return held("RESULT_REJECTED_HOLD", "DEFENDER_TARGET_CHANGED")
        return _classify_protected_defender_result(reply.get("result"), request)
    except ProtectedBrokerHold as exc:
        if exc.code == "PROTECTED_ACTION_OUTCOME_UNKNOWN":
            return DefenderFileScanResult("UNKNOWN_HOLD", request.content_sha256,
                False, None, "DEFENDER_BROKER_OUTCOME_UNKNOWN",
                scan_error_code="BROKER_OUTCOME_UNKNOWN")
        return held("NOT_RUN_HOLD", exc.code)
    except (CodeShieldHold, OSError, ValueError, TypeError, KeyError):
        return held("RESULT_REJECTED_HOLD", "DEFENDER_RESULT_HOLD")


def _verify_microsoft_image(api, image: Path) -> None:
    """Offline WinVerifyTrust + actual leaf publisher, never a name-only pin."""
    import ctypes as c
    from ctypes import wintypes as w
    from my_local_ai.state.consent import ProtectedBrokerHold
    trust = c.WinDLL("wintrust.dll", use_last_error=True, winmode=0x800)
    crypt = c.WinDLL("crypt32.dll", use_last_error=True, winmode=0x800)
    class Guid(c.Structure):
        _fields_ = [("a", w.DWORD), ("b", w.WORD), ("d", w.WORD), ("tail", c.c_ubyte * 8)]
    class FileInfo(c.Structure):
        _fields_ = [("size", w.DWORD), ("path", w.LPCWSTR), ("file", w.HANDLE), ("subject", c.c_void_p)]
    class TrustData(c.Structure):
        _fields_ = [("size", w.DWORD), ("policy", c.c_void_p), ("sip", c.c_void_p),
                    ("ui", w.DWORD), ("revocation", w.DWORD), ("choice", w.DWORD),
                    ("file", c.POINTER(FileInfo)), ("action", w.DWORD), ("state", w.HANDLE),
                    ("url", w.LPCWSTR), ("flags", w.DWORD), ("context", w.DWORD),
                    ("signature_settings", c.c_void_p)]
    class ProviderCert(c.Structure):
        _fields_ = [("size", w.DWORD), ("cert", c.c_void_p)]
    class ProviderSigner(c.Structure):
        _fields_ = [("size", w.DWORD), ("verified_at", w.FILETIME),
                    ("count", w.DWORD), ("chain", c.POINTER(ProviderCert))]
    guid = Guid(0x00AAC56B, 0xCD44, 0x11D0,
                (c.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
    file = FileInfo(c.sizeof(FileInfo), str(image), None, None)
    # WTD_UI_NONE, verify cached chain only; no certificate/network fetch.
    data = TrustData(c.sizeof(TrustData), None, None, 2, 0, 1,
                     c.pointer(file), 1, None, None, 0x1000 | 0x80, 0, None)
    verify = api._bind(trust, "WinVerifyTrust", [w.HWND, c.POINTER(Guid), c.c_void_p], c.c_long)
    try:
        if verify(w.HWND(-1), c.byref(guid), c.byref(data)) != 0:
            raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
        provider = api._bind(trust, "WTHelperProvDataFromStateData", [w.HANDLE], c.c_void_p)(data.state)
        signer_fn = api._bind(trust, "WTHelperGetProvSignerFromChain",
            [c.c_void_p, w.DWORD, w.BOOL, w.DWORD], c.POINTER(ProviderSigner))
        signer = signer_fn(provider, 0, False, 0) if provider else None
        if not signer or signer.contents.count < 1 or not signer.contents.chain:
            raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
        cert = signer.contents.chain[0].cert
        name = c.create_unicode_buffer(256)
        get_name = api._bind(crypt, "CertGetNameStringW",
            [c.c_void_p, w.DWORD, w.DWORD, c.c_void_p, w.LPWSTR, w.DWORD], w.DWORD)
        if not 1 < get_name(cert, 4, 0, None, name, len(name)) < len(name) or name.value != "Microsoft Corporation":
            raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
    finally:
        data.action = 2  # WTD_STATEACTION_CLOSE on every path.
        verify(w.HWND(-1), c.byref(guid), c.byref(data))


def _deny_truncated_defender_events(after_record: int, existing_count: int) -> None:
    """Fail closed if scan-time event history exceeds the bounded capture.

    The pre-scan query is intentionally reverse-ordered: its newest record
    alone establishes the cursor. Post-scan evidence is different: dropping
    even one matching safety/detection event makes CLEAN untrustworthy.
    """
    from my_local_ai.state.consent import ProtectedBrokerHold
    if (type(after_record) is not int or after_record < 0
        or type(existing_count) is not int or existing_count < 0
        or (after_record > 0 and existing_count >= 256)):
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")


def _defender_events_after(api, after_record: int) -> list[dict]:
    """Read bounded event XML via wevtapi. No PowerShell or mutable log file."""
    import xml.etree.ElementTree as ET
    from my_local_ai.state.consent import ProtectedBrokerHold
    c, w = api.c, api.w
    dll = c.WinDLL("wevtapi.dll", use_last_error=True, winmode=0x800)
    query = api._bind(dll, "EvtQuery", [w.HANDLE, w.LPCWSTR, w.LPCWSTR, w.DWORD], w.HANDLE)
    next_fn = api._bind(dll, "EvtNext", [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE),
                                       w.DWORD, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
    render = api._bind(dll, "EvtRender", [w.HANDLE, w.HANDLE, w.DWORD, w.DWORD,
        c.c_void_p, c.POINTER(w.DWORD), c.POINTER(w.DWORD)], w.BOOL)
    close = api._bind(dll, "EvtClose", [w.HANDLE], w.BOOL)
    xpath = "*[System[EventRecordID > " + str(after_record) + "]]"
    handle = query(None, "Microsoft-Windows-Windows Defender/Operational", xpath, 1 | 0x200)
    if not handle:
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    result = []
    ns = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
    try:
        # Oldest records may be omitted only during the pre-scan cursor
        # snapshot. Post-scan queries must probe record 257 and HOLD rather
        # than silently truncate policy-change or malware evidence.
        for _ in range(257 if after_record else 256):
            event, count = w.HANDLE(), w.DWORD()
            if not next_fn(handle, 1, c.byref(event), 1000, 0, c.byref(count)):
                if c.get_last_error() == 259:
                    break
                raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
            try:
                _deny_truncated_defender_events(after_record, len(result))
                length, properties = w.DWORD(), w.DWORD()
                render(None, event, 1, 0, None, c.byref(length), c.byref(properties))
                if not 1 <= length.value <= 65536:
                    raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                buf = c.create_string_buffer(length.value)
                if not render(None, event, 1, len(buf), buf, c.byref(length), c.byref(properties)):
                    raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                xml = c.wstring_at(c.cast(buf, w.LPWSTR))
                tree = ET.fromstring(xml)
                provider = tree.find("e:System/e:Provider", ns)
                if provider is None or provider.attrib.get("Name") != "Microsoft-Windows-Windows Defender":
                    raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                record = int(tree.findtext("e:System/e:EventRecordID", namespaces=ns))
                event_id = int(tree.findtext("e:System/e:EventID", namespaces=ns))
                fields = {}
                for item in tree.findall("e:EventData/e:Data", ns):
                    name = item.attrib.get("Name", "")
                    if name in fields:
                        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                    fields[name] = item.text or ""
                result.append({"record": record, "id": event_id, "fields": fields,
                               "evidence_sha256": _sha256(xml.encode("utf-8")).hexdigest()})
            finally:
                close(event)
    finally:
        close(handle)
    return result


def _defender_completion_evidence(events: list[dict], target: str, cursor: int) -> tuple[bool, list[str]]:
    """Correlate one exact private scan resource and its scan ID; fail closed.

    DisableRemediation may suppress detection events. No detection event with
    exit code 2 is UNKNOWN, not a clean scan. Localized/missing/ambiguous resource
    fields likewise cannot become proof of completion.
    """
    normalized = target.casefold()
    starts = []
    # Normalize only events captured AFTER the pre-scan cursor. A reused
    # scan identifier from another resource cannot complete our custom scan.
    for event in events:
        if event["record"] <= cursor or event["id"] != 1000:
            continue
        resource = event["fields"].get("Scan Resources", "").strip().casefold()
        if resource.startswith("file:_"):
            resource = resource[6:]
        if resource == normalized and event["fields"].get("Scan ID"):
            starts.append(event)
    if len(starts) != 1:
        return False, []
    start = starts[0]
    scan_id = start["fields"]["Scan ID"]
    if any(e["id"] == 1000 and e["record"] > cursor
           and e["record"] != start["record"]
           and e["fields"].get("Scan ID") == scan_id for e in events):
        return False, []  # Ambiguous or reused scan ID.
    related = [e for e in events if e["record"] > start["record"]
               and e["fields"].get("Scan ID") == scan_id]
    completed = (sum(e["id"] == 1001 for e in related) == 1
                 and not any(e["id"] in (1002, 1005) for e in related))
    detections = []
    for event in events:
        if event["record"] <= start["record"] or event["id"] not in (1006, 1116):
            continue
        fields = event["fields"]
        resource = fields.get("Path", "").strip().casefold()
        if resource.startswith("file:_"):
            resource = resource[6:]
        # A same-path detection with no Scan ID cannot be attributed to this
        # one custom-file scan. It must also prevent a spurious CLEAN outcome
        # if the engine happened to exit zero and the 1001 event exists.
        # Explicit *foreign* scan IDs are unrelated; never borrow them.
        if resource != normalized or fields.get("Scan ID") not in (None, "", scan_id):
            continue
        if (fields.get("Scan ID") != scan_id
            or not fields.get("Threat ID") or not fields.get("Threat Name")
            or type(event.get("evidence_sha256")) is not str):
            return False, []
        detections.append(event["evidence_sha256"])
    return completed, detections


def _serve_defender_scan(api, binding: dict, payload: dict, scope: dict, stopped) -> dict:
    """Protected server -> fixed no-remediation custom FILE scan -> evidence.

    No settings/exclusions/CFA/real-time/cloud policy is written. PUBLIC_SYNTHETIC
    is enforced independently. The target is copied into a preprotected private
    directory and held against replacement, with SHA/size readback before/after.
    A CLI timeout never claims that the engine background scan was cancelled.
    """
    import secrets
    import winreg
    from contextlib import ExitStack
    from my_local_ai.state.consent import (
        ProtectedBrokerHold, _SERVICE_HOME, _broker_canonical,
        _run_bounded_fixed_process,
    )
    if (type(payload) is not dict or set(payload) != {
            "context_sha256", "disposable_root", "relative_target", "content_sha256",
            "content_size", "timeout_seconds", "policy"}
        or payload["policy"] != "DEFENDER_CUSTOM_FILE_OFFLINE_DISABLE_REMEDIATION_V1"
        or scope["data_class"] != "PUBLIC_SYNTHETIC"
        or payload["disposable_root"] != scope["disposable_root"]
        or type(payload["timeout_seconds"]) is not int or not 1 <= payload["timeout_seconds"] <= 120
        or type(payload["content_size"]) is not int
        or not 1 <= payload["content_size"] <= _MAX_OWNER_SCAN_BYTES
        or type(payload["content_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", payload["content_sha256"]) is None):
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    relative = checked_relative_path(payload["relative_target"])
    if relative not in scope["allowed_paths"] or Path(relative).suffix.casefold() not in _ALLOWED_SCAN_EXTENSIONS:
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    # No Defender scan when inactive/passive/stale/unavailable. This invokes
    # only the existing fixed read-only status probe, never Start-MpScan.
    if not probe_defender_status().defender_primary_active:
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\MyLocalAI\ProtectedBrokers\v1\scanner", 0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        image_value, image_kind = winreg.QueryValueEx(key, "DefenderPath")
        image_sha, hash_kind = winreg.QueryValueEx(key, "DefenderSha256")
    if (image_kind != winreg.REG_SZ or hash_kind != winreg.REG_SZ
        or type(image_value) is not str or type(image_sha) is not str
        or re.fullmatch(r"[0-9a-f]{64}", image_sha) is None
        or re.fullmatch(r"C:\\(?:Program Files\\Windows Defender|ProgramData\\Microsoft\\Windows Defender\\Platform\\[0-9.\-]+)\\MpCmdRun.exe",
                        image_value, re.IGNORECASE) is None):
        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
    image = Path(image_value)
    source = Path(scope["disposable_root"]) / relative
    stage_dir = _SERVICE_HOME / "scanner"
    reference = secrets.token_hex(16)
    staged = stage_dir / ("scan_" + reference + Path(relative).suffix.lower())
    prior_resources = api.resources
    try:
        with ExitStack() as locks:
            api.resources = locks
            api.pin_path(image)
            if _sha256(image.read_bytes()).hexdigest() != image_sha:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            _verify_microsoft_image(api, image)
            api.lock_untrusted_input(source)
            before_digest, before_size = _read_bounded_untrusted_scan_target(source)
            if before_digest != payload["content_sha256"] or before_size != payload["content_size"]:
                raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
            # Protected parent/ACLs are pre-provisioned; file creation does not
            # grant/change ACLs. No source/executable is ever opened for writing.
            with source.open("rb") as incoming, staged.open("xb") as outgoing:
                copied = 0
                while block := incoming.read(65536):
                    copied += len(block)
                    if copied > _MAX_OWNER_SCAN_BYTES or stopped.is_set():
                        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                    outgoing.write(block)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            api.pin_path(staged, private=True)
            if _read_bounded_untrusted_scan_target(staged) != (before_digest, before_size):
                raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
            prior_events = _defender_events_after(api, 0)
            cursor = max((item["record"] for item in prior_events), default=0)
            root = os.environ.get("SystemRoot", r"C:\Windows")
            env = {"SystemRoot": root, "WINDIR": root,
                   "PATH": str(Path(root) / "System32"),
                   "TEMP": str(stage_dir), "TMP": str(stage_dir)}
            code, stdout, stderr, timed_out = _run_bounded_fixed_process(
                [str(image), "-Scan", "-ScanType", "3", "-File", str(staged), "-DisableRemediation"],
                cwd=image.parent, env=env, timeout_seconds=payload["timeout_seconds"],
                stopped=stopped, output_limit=1024 * 1024,
            )
            after_events = _defender_events_after(api, cursor)
            if any(item["id"] in {5001, 5004, 5007, 5010, 5012} for item in after_events):
                raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
            completed, detections = _defender_completion_evidence(after_events, str(staged), cursor)
            if (_read_bounded_untrusted_scan_target(staged) != (before_digest, before_size)
                or _read_bounded_untrusted_scan_target(source) != (before_digest, before_size)
                or _sha256(image.read_bytes()).hexdigest() != image_sha):
                raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
            result = {"outcome": "UNKNOWN", "content_sha256": before_digest,
                "content_size": before_size, "scan_completed": False, "timed_out": False,
                "finding_count": None, "engine_exit_code": code,
                "scan_error_code": "COMPLETION_NOT_PROVEN", "detection_evidence_sha256": None,
                "remediation": "DISABLED", "policy_changed": False, "scan_reference": reference}
            if timed_out:
                result.update(outcome="TIMEOUT", timed_out=True, engine_exit_code=None,
                              scan_error_code="SCAN_TIMEOUT")
            elif completed and code == 0 and not detections and not stderr:
                result.update(outcome="COMPLETED_CLEAN", scan_completed=True,
                              finding_count=0, scan_error_code=None)
            elif completed and code == 2 and detections:
                evidence = {"events": detections, "stdout_sha256": _sha256(stdout).hexdigest(),
                            "stderr_sha256": _sha256(stderr).hexdigest(), "scan_reference": reference}
                result.update(outcome="MALWARE_DETECTED", scan_completed=True,
                              finding_count=len(detections), scan_error_code=None,
                              detection_evidence_sha256=_sha256(_broker_canonical(evidence)).hexdigest())
            elif code not in (0, 2):
                result.update(outcome="SCAN_ERROR", scan_error_code="DEFENDER_ENGINE_ERROR")
            # Signed by the common service host only after live lease recheck
            # and durable nonce consumption. No raw private paths are returned.
            return result
    finally:
        api.resources = prior_resources
        # Private service scratch only, one exact file; never recursive cleanup.
        try:
            if staged.is_file():
                staged.unlink()
        except OSError:
            pass  # Cleanup failure gives no execution/promotion authority.


if __name__ == "__main__":
    from my_local_ai.state.consent import protected_service_main
    raise SystemExit(protected_service_main("scanner"))
