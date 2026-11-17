"""CodeShield V1.3 pinned local Semgrep CE scanner, Python/JS static only.

No remote registry, login, updates, imported guest code, autofix or test run.
The protected controller must independently authenticate all binary/rule pins,
scope, network isolation and F18 before treating any result as evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess

from .ast_preflight import preflight_changed_paths
from .codeshield_contracts import (
    CodeShieldContext, CodeShieldHold, RiskOutcome, ScanStatus, ScannerEvidence,
)

_MAX_BINARY = 128 * 1024 * 1024
_MAX_RULES = 64 * 1024
_MAX_REPORT = 512 * 1024
_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")


@dataclass(frozen=True)
class SemgrepResult:
    outcome: RiskOutcome
    status: ScanStatus
    reason: str
    finding_count: int
    evidence: ScannerEvidence | None
    execution_granted: bool = False
    f18_verified: bool = False
    remote_upload_performed: bool = False
    can_promote: bool = False


def _digest(path: Path, *, max_size: int) -> str | None:
    try:
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
            or not 1 <= st.st_size <= max_size
            or getattr(st, "st_file_attributes", 0) &
               getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return None
        h = sha256()
        with path.open("rb") as stream:
            while piece := stream.read(65536):
                h.update(piece)
        after = path.lstat()
        if (st.st_ino, st.st_dev, st.st_size, st.st_mtime_ns) != (
            after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns
        ):
            return None
        return h.hexdigest()
    except (OSError, ValueError):
        return None


def _result(
    context: CodeShieldContext, code: ScanStatus, reason: str,
    count: int = 0,
) -> SemgrepResult:
    pins = [p for p in context.scanner_pins if p.tool == "semgrep"]
    pin = pins[0] if pins else None
    evidence = None if pin is None else ScannerEvidence(
        tool="semgrep", version=pin.version,
        binary_sha256=pin.binary_sha256, rules_sha256=pin.rules_sha256,
        context_sha256=context.fingerprint_sha256,
        candidate_git_sha=context.candidate_git_sha,
        status=code, finding_count=count,
    )
    risk = (RiskOutcome.ALLOW_NON_EXECUTING if code == ScanStatus.PASS
            else RiskOutcome.HOLD_HIGH_RISK if code == ScanStatus.FINDINGS
            else RiskOutcome.UNKNOWN_HOLD)
    return SemgrepResult(risk, code, reason, count, evidence)


def run_local_semgrep(
    context: CodeShieldContext, *, executable: str | Path,
    local_rules: str | Path, disposable_worktree: str | Path,
    original_checkout: str | Path, changed_paths: tuple[str, ...],
    owner_protected_no_egress: bool = False, timeout_seconds: int = 20,
) -> SemgrepResult:
    """Pinned local parser process; fail closed absent proven egress barrier.

    owner_protected_no_egress is only a narrow input to an OS-protected caller.
    A guest-supplied True is not an attestation. The default always HOLDs.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    if (type(owner_protected_no_egress) is not bool or type(timeout_seconds) is not int
        or not 1 <= timeout_seconds <= 30):
        raise CodeShieldHold()
    if os.name != "nt":
        return _result(context, ScanStatus.NOT_RUN, "WINDOWS_REQUIRED")
    if owner_protected_no_egress is not True:
        return _result(context, ScanStatus.NOT_RUN, "OS_EGRESS_BOUNDARY_UNPROVEN")
    pins = [p for p in context.scanner_pins if p.tool == "semgrep"]
    if len(pins) != 1 or pins[0].rules_sha256 is None:
        return _result(context, ScanStatus.NOT_RUN, "SEMGREP_PIN_MISSING")
    pin = pins[0]
    try:
        checked = preflight_changed_paths(
            context, worktree=disposable_worktree,
            original_checkout=original_checkout, changed_paths=changed_paths,
        )
        if checked.git_diff_verified or any(
            not p.endswith(_SUFFIXES) for p in changed_paths
        ):
            return _result(context, ScanStatus.ERROR, "UNSAFE_CHANGED_SCOPE")
        exe, rules = Path(executable), Path(local_rules)
        work, original = Path(disposable_worktree), Path(original_checkout)
        if (not exe.is_absolute() or not rules.is_absolute()
            or not work.is_absolute() or not original.is_absolute()
            or any(path in exe.parents or path == exe for path in (work, original))
            or any(path in rules.parents or path == rules for path in (work, original))
            or ".." in exe.parts or ".." in rules.parts
            or exe.suffix.lower() != ".exe" or rules.suffix.lower() not in {".yml", ".yaml"}):
            return _result(context, ScanStatus.ERROR, "UNTRUSTED_TOOL_PATH")
        if (_digest(exe, max_size=_MAX_BINARY) != pin.binary_sha256
            or _digest(rules, max_size=_MAX_RULES) != pin.rules_sha256):
            return _result(context, ScanStatus.ERROR, "TOOL_OR_RULES_HASH_MISMATCH")
        win_root = os.environ["SystemRoot"]
        env = {
            "SystemRoot": win_root, "WINDIR": win_root,
            "PATH": str(Path(win_root) / "System32"),
            "SEMGREP_SEND_METRICS": "off",
            "SEMGREP_ENABLE_VERSION_CHECK": "false",
            "SEMGREP_SETTINGS_FILE": str(work / ".codeshield-not-created"),
            "SEMGREP_LOGGING_LEVEL": "ERROR",
            "PYTHONNOUSERSITE": "1",
        }
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        version = subprocess.run(
            [str(exe), "--version"], shell=False, env=env, cwd=str(work),
            capture_output=True, timeout=min(timeout_seconds, 6),
            check=False, creationflags=flags,
        )
        if (version.returncode or len(version.stdout) > 256
            or version.stdout.decode("ascii", "replace").strip() != pin.version):
            return _result(context, ScanStatus.ERROR, "SEMGREP_VERSION_MISMATCH")
        # No --autofix, registry config, cloud flag, login, CI mode or output file.
        args = [
            str(exe), "scan", "--config", str(rules), "--metrics=off",
            "--disable-version-check", "--json", "--error",
            *(str(work / p) for p in changed_paths),
        ]
        proc = subprocess.run(
            args, shell=False, cwd=str(work), env=env,
            capture_output=True, timeout=timeout_seconds,
            check=False, creationflags=flags,
        )
        if (_digest(exe, max_size=_MAX_BINARY) != pin.binary_sha256
            or _digest(rules, max_size=_MAX_RULES) != pin.rules_sha256
            or proc.returncode not in (0, 1)
            or len(proc.stdout) > _MAX_REPORT or len(proc.stderr) > _MAX_REPORT):
            return _result(context, ScanStatus.ERROR, "SEMGREP_EXECUTION_OR_PIN_CHANGED")
        parsed = json.loads(proc.stdout.decode("utf-8"))
        if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
            return _result(context, ScanStatus.ERROR, "SEMGREP_INVALID_JSON")
        if parsed.get("errors"):
            return _result(context, ScanStatus.ERROR, "SEMGREP_SCANNER_ERRORS")
        found = parsed["results"]
        if len(found) > 10000 or any(not isinstance(x, dict) for x in found):
            return _result(context, ScanStatus.ERROR, "SEMGREP_RESULT_OVERFLOW")
        if (proc.returncode == 1) != bool(found):
            return _result(context, ScanStatus.ERROR, "SEMGREP_FINDING_EXIT_MISMATCH")
        return _result(
            context, ScanStatus.FINDINGS if found else ScanStatus.PASS,
            "SEMGREP_FINDINGS_REDACTED" if found else "SEMGREP_STATIC_ONLY",
            len(found),
        )
    except (OSError, ValueError, KeyError, UnicodeError, subprocess.TimeoutExpired):
        return _result(context, ScanStatus.ERROR, "SEMGREP_UNAVAILABLE_OR_INVALID")
