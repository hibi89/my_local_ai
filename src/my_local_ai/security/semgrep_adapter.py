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
import tempfile

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


_MAX_SOURCE_BYTES = 256 * 1024
_MAX_SOURCES_TOTAL = 1024 * 1024


@dataclass(frozen=True)
class SemgrepBrokerRequest:
    """Pinned data for a fixed local static scanner operator.

    This record is not a runtime owner grant, no-egress OS attestation,
    F18 verdict, or permission to execute generated code.
    """
    context_sha256: str
    candidate_git_sha: str
    binary_sha256: str
    rules_sha256: str
    pinned_version: str
    argv: tuple[str, ...]
    source_sha256: tuple[tuple[str, str], ...]
    allowed_paths: tuple[str, ...]
    timeout_seconds: int
    stage: str = "PINNED_STATIC_TOOL_REQUEST_ONLY"
    can_spawn: bool = False
    network_isolation_attested: bool = False
    host_execution_allowed: bool = False
    f18_verified: bool = False
    owner_go_verified: bool = False

    def __post_init__(self) -> None:
        if (self.stage != "PINNED_STATIC_TOOL_REQUEST_ONLY"
            or not isinstance(self.argv, tuple)
            or len(self.argv) < 9 or len(self.argv) > 40
            or not isinstance(self.source_sha256, tuple)
            or len(self.source_sha256) != len(self.allowed_paths)
            or any(getattr(self, flag) is not False for flag in (
                "can_spawn", "network_isolation_attested",
                "host_execution_allowed", "f18_verified", "owner_go_verified",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def _bounded_source_sha256(path: Path) -> str | None:
    """Hash a non-symlink source file, ensuring identity did not change."""
    try:
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 1 <= before.st_size <= _MAX_SOURCE_BYTES
            or getattr(before, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return None
        flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_BINARY", 0))
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if ((opened.st_dev, opened.st_ino, opened.st_size)
                != (before.st_dev, before.st_ino, before.st_size)):
                return None
            data = stream.read(_MAX_SOURCE_BYTES + 1)
            current = os.fstat(stream.fileno())
        after = path.lstat()
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if (len(data) != before.st_size
            or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                != identity
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != identity):
            return None
        return sha256(data).hexdigest()
    except (OSError, ValueError, OverflowError):
        return None


def _reject_guest_semgrep_ignores(worktree: Path, paths: tuple[str, ...]) -> None:
    """Prevent per-project ignore/config directives from silently skipping files.

    Git ignore is disabled in fixed argv; Semgrep's own ignore files remain a
    separate attack surface until a native broker can verify tool behavior.
    """
    for name in paths:
        parent = (worktree / name).parent
        while True:
            for ignored in (".semgrepignore", ".semgrep.yml", ".semgrep.yaml"):
                target = parent / ignored
                try:
                    target.lstat()
                except FileNotFoundError:
                    continue
                except OSError:
                    raise CodeShieldHold("UNSAFE_PATH") from None
                else:
                    raise CodeShieldHold("UNSAFE_PATH")
            if parent == worktree:
                break
            if parent == parent.parent or worktree not in parent.parents:
                raise CodeShieldHold("UNSAFE_PATH")
            parent = parent.parent


def prepare_protected_semgrep_request(
    context: CodeShieldContext, *, executable: str | Path,
    local_rules: str | Path, disposable_worktree: str | Path,
    original_checkout: str | Path, changed_paths: tuple[str, ...],
    timeout_seconds: int = 20,
) -> SemgrepBrokerRequest:
    """Bounded preflight for an owner-installed, pinned static scanner.

    The request is inert. Model text cannot choose an executable or flags;
    the trusted fixed operator checks its own protected installation root.
    """
    if (not isinstance(context, CodeShieldContext)
        or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30):
        raise CodeShieldHold()
    pins = [p for p in context.scanner_pins if p.tool == "semgrep"]
    if len(pins) != 1 or pins[0].rules_sha256 is None:
        raise CodeShieldHold("UNPINNED_SCANNER")
    pin = pins[0]
    if (not isinstance(changed_paths, tuple) or not changed_paths
        or any(not name.endswith(_SUFFIXES) for name in changed_paths)):
        raise CodeShieldHold("UNSAFE_PATH")
    scoped = preflight_changed_paths(
        context, worktree=disposable_worktree,
        original_checkout=original_checkout, changed_paths=changed_paths,
    )
    if scoped.may_execute or scoped.may_write or scoped.git_diff_verified:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    root, original = Path(disposable_worktree), Path(original_checkout)
    exe, rules = Path(executable), Path(local_rules)
    expected_rules = Path(__file__).parent / "rules" / "codeshield.yaml"
    if (not exe.is_absolute() or not rules.is_absolute()
        or not root.is_absolute() or not original.is_absolute()
        or exe.suffix.casefold() != ".exe"
        or rules != expected_rules
        or any(".." in path.parts for path in (exe, rules, root, original))
        or any(path == exe or path in exe.parents for path in (root, original))
        or exe == rules):
        raise CodeShieldHold("UNPINNED_SCANNER")
    # Do not trust a scanner executable inside the generated worktree.
    # Parent symlinks/reparse aliases must not mask a substituted binary.
    for parent in (exe.parent, *exe.parent.parents, rules.parent, *rules.parent.parents):
        try:
            st = parent.lstat()
        except (OSError, ValueError):
            raise CodeShieldHold("UNPINNED_SCANNER") from None
        if (not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode)
            or getattr(st, "st_file_attributes", 0)
               & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise CodeShieldHold("UNPINNED_SCANNER")
    if (_digest(exe, max_size=_MAX_BINARY) != pin.binary_sha256
        or _digest(rules, max_size=_MAX_RULES) != pin.rules_sha256):
        raise CodeShieldHold("UNPINNED_SCANNER")
    _reject_guest_semgrep_ignores(root, changed_paths)
    digests = []
    for name in changed_paths:
        actual = _bounded_source_sha256(root / name)
        if actual is None:
            raise CodeShieldHold("STALE_EVIDENCE")
        digests.append((name, actual))
    if len(digests) > 16 or sum((root / name).stat().st_size for name in changed_paths) > _MAX_SOURCES_TOTAL:
        raise CodeShieldHold("UNSAFE_PATH")
    # Request only; the caller cannot use or change these argv to run a tool.
    argv = (
        str(exe), "scan", "--config", str(rules), "--metrics=off",
        "--disable-version-check", "--no-git-ignore", "--disable-nosem",
        "--jobs=1", "--max-target-bytes=262144", "--json", "--error", "--",
        *(str(root / name) for name in changed_paths),
    )
    return SemgrepBrokerRequest(
        context.fingerprint_sha256, context.candidate_git_sha,
        pin.binary_sha256, pin.rules_sha256, pin.version,
        argv, tuple(digests), changed_paths, timeout_seconds,
    )


def read_untrusted_semgrep_report(
    request: SemgrepBrokerRequest, raw: bytes,
    *, exit_code: int,
) -> SemgrepResult:
    """Parse bounded guest/broker JSON; findings may increase HOLD only.

    Even a clean JSON result is UNKNOWN_HOLD because a Python object and an
    exit code cannot prove protected OS egress or independent F18 review.
    """
    if (not isinstance(request, SemgrepBrokerRequest)
        or not isinstance(raw, bytes) or len(raw) > _MAX_REPORT
        or type(exit_code) is not int or exit_code not in (0, 1)):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    from my_local_ai.state.consent import _broker_decode, ProtectedBrokerHold
    try:
        data = _broker_decode(raw)
    except ProtectedBrokerHold:
        raise CodeShieldHold("UNTRUSTED_DECISION") from None
    if (not isinstance(data, dict) or not isinstance(data.get("results"), list)
        or not isinstance(data.get("errors", []), list) or data.get("errors")):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    findings = data["results"]
    if len(findings) > 10000:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    import ntpath
    allowed = set(request.allowed_paths)
    root = request.argv[-len(request.allowed_paths):]
    accepted = {
        ntpath.normcase(ntpath.normpath(path)) for path in root
    }
    accepted.update(ntpath.normcase(ntpath.normpath(path)) for path in allowed)
    for item in findings:
        if (not isinstance(item, dict)
            or not isinstance(item.get("check_id"), str)
            or not 1 <= len(item["check_id"]) <= 160
            or not isinstance(item.get("path"), str)
            or ntpath.normcase(ntpath.normpath(item["path"])) not in accepted
            or not isinstance(item.get("start"), dict)
            or type(item["start"].get("line")) is not int
            or not 1 <= item["start"]["line"] <= 1000000):
            raise CodeShieldHold("UNTRUSTED_DECISION")
    if (exit_code == 1) != bool(findings):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    # NEVER create ScannerEvidence from unauthenticated result contents.
    return SemgrepResult(
        RiskOutcome.HOLD_HIGH_RISK if findings else RiskOutcome.UNKNOWN_HOLD,
        ScanStatus.FINDINGS if findings else ScanStatus.NOT_RUN,
        "UNTRUSTED_SEMGREP_FINDINGS" if findings else "CLEAN_REPORT_NOT_OS_ATTESTED",
        len(findings), None,
    )


def _is_trusted_fixed_semgrep_path(path: Path) -> bool:
    """Only a machine-managed vendor tool location; never a user worktree exe.

    The observed ProgramFiles location is not proof of vendor authenticity;
    exact binary SHA is also required, and real Windows signature/ACL tests
    remain P2. No PATH, user profile, temporary or downloaded exe fallback.
    """
    import re
    if os.name != "nt":
        return False
    program_files = os.environ.get("ProgramFiles", "")
    if not re.fullmatch(r"[A-Za-z]:\\\\Program Files", program_files, re.IGNORECASE):
        return False
    expected = Path(program_files) / "Semgrep" / "semgrep.exe"
    return path == expected


def _run_pinned_semgrep_static_operator(
    context: CodeShieldContext, request: SemgrepBrokerRequest, *,
    executable: Path, rules: Path, disposable_worktree: Path,
) -> SemgrepResult:
    """Actual Semgrep CE static scan on public/synthetic text, never code run.

    No VM, container, shell or guest. The vendor CLI is a fixed trusted
    operator; firewall-enforced no-egress is NOT attested. Hence this path
    refuses private/customer data and never creates an F18/runtime grant.
    """
    from .codeshield_contracts import DataClass
    from my_local_ai.state.consent import _broker_decode, ProtectedBrokerHold
    if (context.data_class != DataClass.PUBLIC_SYNTHETIC
        or not _is_trusted_fixed_semgrep_path(executable)):
        return _result(context, ScanStatus.NOT_RUN, "TRUSTED_STATIC_OPERATOR_SCOPE_HOLD")
    if (request.can_spawn or request.network_isolation_attested
        or request.owner_go_verified or request.f18_verified
        or request.stage != "PINNED_STATIC_TOOL_REQUEST_ONLY"):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    root = disposable_worktree
    if (_digest(executable, max_size=_MAX_BINARY) != request.binary_sha256
        or _digest(rules, max_size=_MAX_RULES) != request.rules_sha256
        or any(_bounded_source_sha256(root / name) != digest
               for name, digest in request.source_sha256)):
        return _result(context, ScanStatus.ERROR, "PIN_OR_SOURCE_CHANGED_HOLD")
    # Minimal process environment; no inherited secrets/SDK credentials.
    # Proxy hints & Semgrep options reduce accidental calls but do NOT prove
    # kernel-enforced network isolation, and cannot be treated as such.
    systemroot = os.environ.get("SystemRoot", "")
    if not systemroot or not Path(systemroot).is_absolute():
        return _result(context, ScanStatus.NOT_RUN, "INVALID_NATIVE_SYSTEMROOT")
    env = {
        "SystemRoot": systemroot,
        "WINDIR": systemroot,
        "PATH": str(Path(systemroot) / "System32"),
        "SEMGREP_SEND_METRICS": "off",
        "SEMGREP_ENABLE_VERSION_CHECK": "0",
        "SEMGREP_APP_TOKEN": "",
        "NO_COLOR": "1",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "",
    }
    try:
        # Keep stdout bounded even if a malicious source produces huge output.
        with tempfile.TemporaryFile(mode="w+b") as output:
            completed = subprocess.run(
                list(request.argv), cwd=str(root), env=env,
                stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.DEVNULL, shell=False, check=False,
                timeout=request.timeout_seconds,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode not in (0, 1) or output.tell() > _MAX_REPORT:
                return _result(context, ScanStatus.ERROR, "STATIC_SCAN_ERROR_HOLD")
            output.seek(0)
            raw = output.read(_MAX_REPORT + 1)
        report = _broker_decode(raw)
        if (not isinstance(report.get("results"), list)
            or not isinstance(report.get("errors"), list)
            or report["errors"]
            or not isinstance(report.get("paths"), dict)
            or report["paths"].get("skipped") != []):
            return _result(context, ScanStatus.ERROR, "INCOMPLETE_STATIC_COVERAGE_HOLD")
        import ntpath
        scanned = report["paths"].get("scanned")
        expected = [str(root / name) for name in request.allowed_paths]
        if (not isinstance(scanned, list)
            or len(scanned) != len(expected)
            or {ntpath.normcase(ntpath.normpath(v)) for v in scanned
                if isinstance(v, str)}
               != {ntpath.normcase(ntpath.normpath(v)) for v in expected}):
            return _result(context, ScanStatus.ERROR, "INCOMPLETE_STATIC_COVERAGE_HOLD")
        # Bounded, strict result-shape check already refuses forged paths,
        # duplicate JSON keys and mismatched finding exit codes.
        parsed = read_untrusted_semgrep_report(
            request, raw, exit_code=completed.returncode,
        )
        if (any(_bounded_source_sha256(root / name) != digest
                for name, digest in request.source_sha256)
            or _digest(executable, max_size=_MAX_BINARY) != request.binary_sha256
            or _digest(rules, max_size=_MAX_RULES) != request.rules_sha256):
            return _result(context, ScanStatus.ERROR, "STATIC_INPUT_CHANGED_HOLD")
        return _result(
            context, ScanStatus.FINDINGS if parsed.finding_count else ScanStatus.PASS,
            "LOCAL_STATIC_FINDINGS_ONLY" if parsed.finding_count
            else "LOCAL_STATIC_PASS_NO_RUNTIME_AUTHORITY",
            parsed.finding_count,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError, TypeError,
            ProtectedBrokerHold, CodeShieldHold):
        return _result(context, ScanStatus.ERROR, "LOCAL_STATIC_SCAN_ERROR_HOLD")


def run_local_semgrep(
    context: CodeShieldContext, *, executable: str | Path,
    local_rules: str | Path, disposable_worktree: str | Path,
    original_checkout: str | Path, changed_paths: tuple[str, ...],
    owner_protected_no_egress: bool = False, timeout_seconds: int = 20,
) -> SemgrepResult:
    """Validate exact public/synthetic inputs then run fixed static tool only.

    Legacy owner_protected_no_egress boolean is inert, never a grant.
    A clean scan is a P1 static observation, NOT F18 or OS no-egress proof.
    """
    from .codeshield_contracts import DataClass
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    if type(owner_protected_no_egress) is not bool:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    if os.name != "nt":
        return _result(context, ScanStatus.NOT_RUN, "WINDOWS_REQUIRED")
    if context.data_class != DataClass.PUBLIC_SYNTHETIC:
        return _result(context, ScanStatus.NOT_RUN, "PUBLIC_SYNTHETIC_ONLY_HOLD")
    if not _is_trusted_fixed_semgrep_path(Path(executable)):
        return _result(context, ScanStatus.NOT_RUN, "UNTRUSTED_SCANNER_LOCATION_HOLD")
    try:
        request = prepare_protected_semgrep_request(
            context, executable=executable, local_rules=local_rules,
            disposable_worktree=disposable_worktree,
            original_checkout=original_checkout,
            changed_paths=changed_paths, timeout_seconds=timeout_seconds,
        )
    except (CodeShieldHold, OSError, ValueError, TypeError):
        return _result(context, ScanStatus.ERROR, "SEMGREP_INPUT_OR_PIN_HOLD")
    return _run_pinned_semgrep_static_operator(
        context, request, executable=Path(executable), rules=Path(local_rules),
        disposable_worktree=Path(disposable_worktree),
    )


@dataclass(frozen=True)
class SemgrepRulesInspection:
    """Non-executing local rules pin check, NOT a Semgrep scan receipt."""
    state: str
    rules_sha256: str | None
    expected_rules_sha256: str | None
    can_execute_scanner: bool = False
    can_execute_candidate: bool = False
    independent_f18_verified: bool = False

    def __post_init__(self) -> None:
        if (self.state not in {"LOCAL_RULES_PINNED_STATIC_ONLY", "UNKNOWN_HOLD"}
            or any(getattr(self, field) is not False for field in (
                "can_execute_scanner", "can_execute_candidate",
                "independent_f18_verified",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def inspect_packaged_semgrep_rules(context: CodeShieldContext) -> SemgrepRulesInspection:
    """Match only the packaged CodeShield YAML to the trusted-side rule pin.

    No registry/YAML evaluation, no Semgrep binary invocation, no network.
    The caller's pin is still merely data until independently authenticated.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    pin = next((p for p in context.scanner_pins if p.tool == "semgrep"), None)
    expected = pin.rules_sha256 if pin is not None else None
    packaged = Path(__file__).parent / "rules" / "codeshield.yaml"
    actual = _digest(packaged, max_size=_MAX_RULES)
    valid = expected is not None and actual == expected
    return SemgrepRulesInspection(
        "LOCAL_RULES_PINNED_STATIC_ONLY" if valid else "UNKNOWN_HOLD",
        actual, expected,
    )


