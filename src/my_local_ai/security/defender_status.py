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


# CS-SWU-012: create a *non-executing* owner-action request. The Controller
# cannot authenticate an owner grant or F18 with user/model-supplied booleans.
from hashlib import sha256 as _sha256
import stat as _stat

from .codeshield_contracts import (
    CodeShieldContext, checked_relative_path,
)
from .ast_preflight import preflight_changed_paths

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
        states = {"COMPLETED_CLEAN", "MALWARE_DETECTED_HOLD", "SCAN_ERROR_HOLD",
                  "SCAN_TIMEOUT_HOLD", "NOT_RUN_HOLD", "RESULT_REJECTED_HOLD"}
        if (self.state not in states
            or type(self.content_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) is None
            or type(self.scan_completed) is not bool
            or self.state == "COMPLETED_CLEAN" and (not self.scan_completed
                or type(self.finding_count) is not int or self.finding_count != 0)
            or self.state == "MALWARE_DETECTED_HOLD" and (not self.scan_completed
                or type(self.finding_count) is not int or self.finding_count <= 0)
            or self.state in {"SCAN_ERROR_HOLD", "SCAN_TIMEOUT_HOLD",
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
    if outcome == "SCAN_ERROR":
        if (completed is not False or timed_out is not False or count is not None
            or type(exit_code) is not int or exit_code == 0
            or not isinstance(error_code, str)
            or re.fullmatch(r"[A-Z0-9_]{3,64}", error_code) is None
            or evidence is not None):
            return rejected()
        return DefenderFileScanResult(
            "SCAN_ERROR_HOLD", request.content_sha256, False, None,
            "DEFENDER_SCAN_ERROR", result["scan_reference"], error_code,
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
        return held("NOT_RUN_HOLD", exc.code)
    except (CodeShieldHold, OSError, ValueError, TypeError, KeyError):
        return held("RESULT_REJECTED_HOLD", "DEFENDER_RESULT_HOLD")
