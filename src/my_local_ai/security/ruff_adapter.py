"""Offline pinned Ruff S/F/E checker for CodeShield; never runs guest code.

Protected caller must supply and independently pin the trusted binary, exact
source Git/worktree and scope. Scanner PASS permits static work only, not F18.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from .ast_preflight import preflight_changed_paths
from .codeshield_contracts import (
    CodeShieldContext, CodeShieldHold, RiskOutcome, ScanStatus,
    ScannerEvidence, ScannerPin,
)

_MAX_EXE_BYTES = 128 * 1024 * 1024
_MAX_REPORT_BYTES = 512 * 1024
_RULES = "E4,E7,E9,F,S"


@dataclass(frozen=True)
class RuffScanResult:
    outcome: RiskOutcome
    status: ScanStatus
    reason: str
    finding_count: int
    evidence: ScannerEvidence | None
    guest_code_executed: bool = False
    can_run_untrusted: bool = False
    may_promote: bool = False
    f18_independently_verified: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.outcome, RiskOutcome)
            or not isinstance(self.status, ScanStatus)
            or self.guest_code_executed is not False
            or self.can_run_untrusted is not False
            or self.may_promote is not False
            or self.f18_independently_verified is not False):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def _pin(context: CodeShieldContext) -> ScannerPin | None:
    return next((p for p in context.scanner_pins if p.tool == "ruff"), None)


def _binary_digest(path: Path) -> str | None:
    """Read a regular pinned file with before/after identity and size fence."""
    try:
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or getattr(before, "st_file_attributes", 0) &
               getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or not 1024 <= before.st_size <= _MAX_EXE_BYTES):
            return None
        h = sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                h.update(chunk)
        after = path.lstat()
        if (before.st_size, before.st_ino, before.st_dev, before.st_mtime_ns) != (
            after.st_size, after.st_ino, after.st_dev, after.st_mtime_ns
        ):
            return None
        return h.hexdigest()
    except (OSError, ValueError):
        return None


def _result(
    context: CodeShieldContext, pin: ScannerPin | None, status: ScanStatus,
    reason: str, findings: int = 0,
) -> RuffScanResult:
    evidence = None if pin is None else ScannerEvidence(
        tool="ruff", version=pin.version,
        binary_sha256=pin.binary_sha256, rules_sha256=pin.rules_sha256,
        context_sha256=context.fingerprint_sha256,
        candidate_git_sha=context.candidate_git_sha,
        status=status, finding_count=findings,
    )
    outcome = (
        RiskOutcome.ALLOW_NON_EXECUTING if status == ScanStatus.PASS else
        RiskOutcome.HOLD_HIGH_RISK if status == ScanStatus.FINDINGS else
        RiskOutcome.UNKNOWN_HOLD
    )
    return RuffScanResult(outcome, status, reason, findings, evidence)


def run_ruff_static(
    context: CodeShieldContext, *, binary: str | Path,
    worktree: str | Path, original_checkout: str | Path,
    python_paths: tuple[str, ...], timeout_seconds: int = 15,
) -> RuffScanResult:
    """Verify native executable digest/version, then scan only scoped Python.

    No shell, guest command, install, rules registry, project configuration,
    network calls or auto-update. Linux/synthetic environment holds by default.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
        raise CodeShieldHold()
    pin = _pin(context)
    if pin is None:
        return _result(context, None, ScanStatus.NOT_RUN, "RUFF_PIN_MISSING")
    if pin.rules_sha256 is not None:
        return _result(context, pin, ScanStatus.ERROR, "RUFF_RULE_PIN_UNEXPECTED")
    if os.name != "nt":
        return _result(context, pin, ScanStatus.NOT_RUN, "WINDOWS_NOT_TESTED")
    try:
        preflight_changed_paths(
            context, worktree=worktree, original_checkout=original_checkout,
            changed_paths=python_paths,
        )
    except (CodeShieldHold, ValueError):
        return _result(context, pin, ScanStatus.ERROR, "PATH_HOLD")
    if any(not path.endswith(".py") for path in python_paths):
        return _result(context, pin, ScanStatus.ERROR, "NON_PYTHON_SCOPE")
    exe, root, original = Path(binary), Path(worktree), Path(original_checkout)
    if (not exe.is_absolute() or not root.is_absolute() or not original.is_absolute()
        or exe == root or exe == original or root in exe.parents
        or original in exe.parents or ".." in exe.parts):
        return _result(context, pin, ScanStatus.ERROR, "UNTRUSTED_BINARY_PATH")
    if _binary_digest(exe) != pin.binary_sha256:
        return _result(context, pin, ScanStatus.ERROR, "RUFF_BINARY_MISMATCH")
    try:
        win_root = os.environ["SystemRoot"]
        env = {
            "SystemRoot": win_root, "WINDIR": win_root,
            "PATH": str(Path(win_root) / "System32"),
            "RUFF_NO_CACHE": "1",
        }
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        version = subprocess.run(
            [str(exe), "--version"], shell=False, cwd=str(root),
            env=env, capture_output=True, timeout=min(5, timeout_seconds),
            check=False, creationflags=flags,
        )
        if (version.returncode != 0 or len(version.stdout) > 256
            or version.stdout.decode("ascii", errors="replace").strip()
            != "ruff " + pin.version):
            return _result(context, pin, ScanStatus.ERROR, "RUFF_VERSION_MISMATCH")
        command = [
            str(exe), "check", "--isolated", "--no-cache",
            "--output-format", "json", "--select", _RULES, "--",
            *(str(root / path) for path in python_paths),
        ]
        completed = subprocess.run(
            command, cwd=str(root), shell=False, env=env,
            capture_output=True, timeout=timeout_seconds, check=False,
            creationflags=flags,
        )
        if _binary_digest(exe) != pin.binary_sha256:
            return _result(context, pin, ScanStatus.ERROR, "RUFF_BINARY_CHANGED")
        if (completed.returncode not in (0, 1)
            or len(completed.stdout) > _MAX_REPORT_BYTES
            or len(completed.stderr) > _MAX_REPORT_BYTES):
            return _result(context, pin, ScanStatus.ERROR, "RUFF_EXIT_OR_REPORT_LIMIT")
        issues = json.loads(completed.stdout.decode("utf-8"))
        if (not isinstance(issues, list) or len(issues) > 10000
            or any(not isinstance(x, dict)
                   or not re.fullmatch(r"[A-Z]{1,3}[0-9]{3,4}",
                                       str(x.get("code", "")))
                   for x in issues)):
            return _result(context, pin, ScanStatus.ERROR, "RUFF_INVALID_REPORT")
        if completed.returncode != (1 if issues else 0):
            return _result(context, pin, ScanStatus.ERROR, "RUFF_EXIT_FINDING_MISMATCH")
        return _result(
            context, pin, ScanStatus.FINDINGS if issues else ScanStatus.PASS,
            "RUFF_FINDINGS_REDACTED" if issues else "RUFF_STATIC_NO_FINDINGS",
            len(issues),
        )
    except (OSError, KeyError, UnicodeError, ValueError, json.JSONDecodeError,
            subprocess.TimeoutExpired):
        return _result(context, pin, ScanStatus.ERROR, "RUFF_TOOL_ERROR")
