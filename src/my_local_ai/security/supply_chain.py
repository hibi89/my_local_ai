"""Pinned local secret and fully offline dependency scans.

No install, Git hooks, package managers, network/API, fix action, remote share,
raw finding logs or guest-supplied command. Scanner PASS is not F18/owner GO.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from .ast_preflight import preflight_changed_paths
from .codeshield_contracts import (
    CodeShieldContext, CodeShieldHold, RiskOutcome, ScanStatus, ScannerEvidence,
)

_MAX_SOURCE = 256 * 1024
_MAX_REPORT = 256 * 1024
_MAX_BINARY = 128 * 1024 * 1024
_LOCKFILES = frozenset({
    "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml",
    "yarn.lock", "poetry.lock", "Pipfile.lock", "uv.lock",
    "Cargo.lock", "go.mod",
})
_LOCKFILE_DB = {
    "package-lock.json": "npm", "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "npm", "yarn.lock": "npm",
    "poetry.lock": "PyPI", "Pipfile.lock": "PyPI", "uv.lock": "PyPI",
    "Cargo.lock": "crates.io", "go.mod": "Go",
}


@dataclass(frozen=True)
class SupplyChainResult:
    scanner: str
    outcome: RiskOutcome
    scan_status: ScanStatus
    reason: str
    finding_count: int
    evidence: ScannerEvidence | None
    can_execute_dependencies: bool = False
    can_publish: bool = False
    f18_verified: bool = False


def _emit(
    ctx: CodeShieldContext, tool: str, status: ScanStatus,
    reason: str, count: int = 0,
) -> SupplyChainResult:
    pins = [p for p in ctx.scanner_pins if p.tool == tool]
    pin = pins[0] if len(pins) == 1 else None
    evidence = None if pin is None else ScannerEvidence(
        tool=tool, version=pin.version, binary_sha256=pin.binary_sha256,
        rules_sha256=pin.rules_sha256,
        context_sha256=ctx.fingerprint_sha256,
        candidate_git_sha=ctx.candidate_git_sha, status=status, finding_count=count,
    )
    risk = (RiskOutcome.ALLOW_NON_EXECUTING if status == ScanStatus.PASS
            else RiskOutcome.HOLD_HIGH_RISK if status == ScanStatus.FINDINGS
            else RiskOutcome.UNKNOWN_HOLD)
    return SupplyChainResult(tool, risk, status, reason, count, evidence)


def _file_sha(path: Path, limit: int) -> str | None:
    try:
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 1 <= before.st_size <= limit
            or getattr(before, "st_file_attributes", 0) &
               getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return None
        digest = sha256()
        with path.open("rb") as stream:
            while piece := stream.read(65536):
                digest.update(piece)
        after = path.lstat()
        if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) != (
            after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size
        ):
            return None
        return digest.hexdigest()
    except (OSError, ValueError):
        return None


def _trusted_exe(ctx: CodeShieldContext, binary: Path, tool: str) -> bool:
    pin = next((p for p in ctx.scanner_pins if p.tool == tool), None)
    if pin is None or not binary.is_absolute() or binary.suffix.casefold() != ".exe":
        return False
    return _file_sha(binary, _MAX_BINARY) == pin.binary_sha256


def _environment(*, offline_db: str | None = None) -> dict[str, str]:
    root = os.environ["SystemRoot"]
    env = {
        "SystemRoot": root, "WINDIR": root,
        "PATH": str(Path(root) / "System32"),
        "HOME": str(Path(root) / "Temp"),
        "USERPROFILE": str(Path(root) / "Temp"),
    }
    if offline_db is not None:
        env["OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY"] = offline_db
    return env


def scan_gitleaks_stdin(
    context: CodeShieldContext, *, binary: str | Path,
    worktree: str | Path, original_checkout: str | Path,
    changed_paths: tuple[str, ...], timeout_seconds: int = 12,
) -> SupplyChainResult:
    """Stream scoped source to pinned Gitleaks CLI; stdout/stderr never exposed.

    Secret findings are represented only as FOUND, not secret text or offsets.
    This scans candidate contents only; pre-push trusted Git history scan is
    separately required before external publication.
    """
    if not isinstance(context, CodeShieldContext) or type(timeout_seconds) is not int:
        raise CodeShieldHold()
    if not 1 <= timeout_seconds <= 20:
        raise CodeShieldHold()
    if os.name != "nt":
        return _emit(context, "gitleaks", ScanStatus.NOT_RUN, "WINDOWS_REQUIRED")
    exe = Path(binary)
    work = Path(worktree)
    original = Path(original_checkout)
    pin = next((p for p in context.scanner_pins if p.tool == "gitleaks"), None)
    if (pin is None or not _trusted_exe(context, exe, "gitleaks")
        or any(x == exe or x in exe.parents for x in (work, original))
        or ".." in exe.parts):
        return _emit(context, "gitleaks", ScanStatus.ERROR, "GITLEAKS_PIN_OR_PATH_HOLD")
    try:
        preflight_changed_paths(
            context, worktree=work, original_checkout=original,
            changed_paths=changed_paths,
        )
        env = _environment()
        # Verify pinned CLI version. No guest CLI, no temp reports or log leaks.
        version = subprocess.run(
            [str(exe), "version"], cwd=str(exe.parent), shell=False,
            env=env, capture_output=True, check=False, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if (version.returncode or len(version.stdout) > 200
            or version.stdout.decode("utf-8", "replace").strip() != pin.version):
            return _emit(context, "gitleaks", ScanStatus.ERROR, "GITLEAKS_VERSION_HOLD")
        for relative in changed_paths:
            src = work / relative
            if _file_sha(src, _MAX_SOURCE) is None:
                return _emit(context, "gitleaks", ScanStatus.ERROR, "SOURCE_CHANGED_OR_TOO_LARGE")
            # This is data streamed as stdin: shell=False; no import or guest code.
            source_bytes = src.read_bytes()
            proc = subprocess.run(
                [str(exe), "stdin", "--redact=100", "--no-banner"],
                input=source_bytes, cwd=str(exe.parent), shell=False, env=env,
                capture_output=True, check=False, timeout=timeout_seconds,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if (_file_sha(src, _MAX_SOURCE) != sha256(source_bytes).hexdigest()
                or _file_sha(exe, _MAX_BINARY) != pin.binary_sha256):
                return _emit(context, "gitleaks", ScanStatus.ERROR, "SCAN_INPUT_CHANGED")
            if len(proc.stdout) > _MAX_REPORT or len(proc.stderr) > _MAX_REPORT:
                return _emit(context, "gitleaks", ScanStatus.ERROR, "GITLEAKS_REPORT_LIMIT")
            # Exit 1 is only a conservative secret FOUND indicator;
            # do not serialize secret or count details from raw findings.
            if proc.returncode == 1:
                return _emit(context, "gitleaks", ScanStatus.FINDINGS,
                             "SECRET_PATTERN_REDACTED", 1)
            if proc.returncode != 0:
                return _emit(context, "gitleaks", ScanStatus.ERROR, "GITLEAKS_TOOL_ERROR")
        return _emit(context, "gitleaks", ScanStatus.PASS, "LOCAL_SECRETS_SCAN_ONLY")
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return _emit(context, "gitleaks", ScanStatus.ERROR, "GITLEAKS_UNAVAILABLE")


@dataclass(frozen=True)
class OfflineDatabasePin:
    ecosystem: str
    zip_sha256: str
    checked_at_utc: datetime
    maximum_age_days: int = 7

    def __post_init__(self) -> None:
        if self.ecosystem not in {"PyPI", "npm", "Go", "crates.io"}:
            raise CodeShieldHold("UNPINNED_SCANNER")
        if not isinstance(self.zip_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.zip_sha256
        ):
            raise CodeShieldHold("UNPINNED_SCANNER")
        if (not isinstance(self.checked_at_utc, datetime)
            or self.checked_at_utc.tzinfo is None
            or type(self.maximum_age_days) is not int
            or not 1 <= self.maximum_age_days <= 30):
            raise CodeShieldHold("UNPINNED_SCANNER")


def scan_osv_offline(
    context: CodeShieldContext, *, binary: str | Path,
    worktree: str | Path, original_checkout: str | Path,
    changed_lockfile: str, local_cache: str | Path,
    database_pin: OfflineDatabasePin, timeout_seconds: int = 20,
) -> SupplyChainResult:
    """Offline-only OSV V2 scan of an allowlisted changed dependency lockfile.

    No database downloads or package manager resolution. Missing local
    database, stale pin, tool incompatibility or malformed output => HOLD.
    """
    if not isinstance(context, CodeShieldContext) or type(timeout_seconds) is not int:
        raise CodeShieldHold()
    if not 1 <= timeout_seconds <= 30:
        raise CodeShieldHold()
    if os.name != "nt":
        return _emit(context, "osv", ScanStatus.NOT_RUN, "WINDOWS_REQUIRED")
    exe, work, original = Path(binary), Path(worktree), Path(original_checkout)
    pin = next((p for p in context.scanner_pins if p.tool == "osv"), None)
    if (pin is None or not _trusted_exe(context, exe, "osv")
        or any(x == exe or x in exe.parents for x in (work, original))):
        return _emit(context, "osv", ScanStatus.ERROR, "OSV_PIN_OR_PATH_HOLD")
    if (not isinstance(changed_lockfile, str)
        or changed_lockfile.rsplit("/", 1)[-1] not in _LOCKFILES):
        return _emit(context, "osv", ScanStatus.ERROR, "LOCKFILE_SCOPE_HOLD")
    if (not isinstance(database_pin, OfflineDatabasePin)
        or database_pin.ecosystem != _LOCKFILE_DB[
            changed_lockfile.rsplit("/", 1)[-1]
        ]):
        return _emit(context, "osv", ScanStatus.ERROR, "WRONG_LOCKFILE_ECOSYSTEM")
    try:
        preflight_changed_paths(
            context, worktree=work, original_checkout=original,
            changed_paths=(changed_lockfile,),
        )
        cache = Path(local_cache)
        if (not cache.is_absolute() or ".." in cache.parts or
            cache == work or cache in work.parents or work in cache.parents or
            cache == original or cache in original.parents or original in cache.parents):
            return _emit(context, "osv", ScanStatus.ERROR, "DB_ROOT_SCOPE_HOLD")
        cache_check = inspect_osv_offline_cache(
            database_pin, cache_root=cache, worktree=work,
            original_checkout=original,
        )
        if cache_check.state != "CACHE_PIN_MATCH_STATIC_ONLY":
            return _emit(context, "osv", ScanStatus.ERROR, "OFFLINE_DB_STALE_OR_INVALID")
        database_file = cache / "osv-scalibr" / database_pin.ecosystem / "all.zip"
        src = work / changed_lockfile
        before = _file_sha(src, _MAX_SOURCE)
        if before is None:
            return _emit(context, "osv", ScanStatus.ERROR, "LOCKFILE_CHANGED_OR_TOO_LARGE")
        # Do not allow untrusted project-level ignore/override files to hide CVEs.
        # Explicit -L is the only source; refuse all local osv-scanner.toml
        # ancestors until a separately pinned trusted --config is implemented.
        parent = src.parent
        while True:
            config = parent / "osv-scanner.toml"
            try:
                config.lstat()
            except FileNotFoundError:
                pass
            except OSError:
                return _emit(context, "osv", ScanStatus.ERROR, "CONFIG_READ_HOLD")
            else:
                return _emit(context, "osv", ScanStatus.ERROR, "UNTRUSTED_OSV_CONFIG")
            if parent == work:
                break
            if parent == parent.parent or work not in parent.parents:
                return _emit(context, "osv", ScanStatus.ERROR, "CONFIG_PARENT_ESCAPE")
            parent = parent.parent
        env = _environment(offline_db=str(cache))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        version = subprocess.run(
            [str(exe), "--version"], cwd=str(exe.parent), shell=False,
            env=env, capture_output=True, check=False, timeout=5,
            creationflags=flags,
        )
        if (version.returncode != 0 or len(version.stdout) > 256
            or pin.version not in version.stdout.decode("ascii", "replace")):
            return _emit(context, "osv", ScanStatus.ERROR, "OSV_VERSION_HOLD")
        process = subprocess.run(
            [str(exe), "--offline", "scan", "source",
             "--no-resolve", "--no-call-analysis=go",
             "--no-call-analysis=rust", "--format=json",
             "--lockfile", str(src)],
            cwd=str(exe.parent), env=env, shell=False, capture_output=True,
            check=False, timeout=timeout_seconds, creationflags=flags,
        )
        if (_file_sha(src, _MAX_SOURCE) != before
            or _file_sha(database_file, _MAX_BINARY) != database_pin.zip_sha256
            or _file_sha(exe, _MAX_BINARY) != pin.binary_sha256):
            return _emit(context, "osv", ScanStatus.ERROR, "OSV_INPUT_CHANGED")
        if (process.returncode not in (0, 1)
            or len(process.stdout) > _MAX_REPORT
            or len(process.stderr) > _MAX_REPORT):
            return _emit(context, "osv", ScanStatus.ERROR, "OSV_EXIT_OR_SIZE")
        doc = json.loads(process.stdout.decode("utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
            return _emit(context, "osv", ScanStatus.ERROR, "OSV_INVALID_REPORT")
        # V2 results contain sources/packages; they are not vulnerability
        # counts. Only count package.vulnerabilities, and reject malformed,
        # empty or mismatched source data instead of manufacturing PASS.
        result_items = doc["results"]
        if len(result_items) > 10000:
            return _emit(context, "osv", ScanStatus.ERROR, "OSV_RESULT_LIMIT")
        findings = 0
        packages_seen = 0
        for record in result_items:
            if not isinstance(record, dict):
                return _emit(context, "osv", ScanStatus.ERROR, "OSV_INVALID_RECORD")
            source = record.get("source")
            packages = record.get("packages")
            if (not isinstance(source, dict)
                or source.get("type") != "lockfile"
                or not isinstance(source.get("path"), str)
                or os.path.normcase(os.path.normpath(source["path"]))
                   != os.path.normcase(os.path.normpath(str(src)))
                or not isinstance(packages, list) or len(packages) > 20000):
                return _emit(context, "osv", ScanStatus.ERROR, "OSV_WRONG_SOURCE")
            for pkg in packages:
                if not isinstance(pkg, dict) or not isinstance(pkg.get("package"), dict):
                    return _emit(context, "osv", ScanStatus.ERROR, "OSV_BAD_PACKAGE")
                vulnerabilities = pkg.get("vulnerabilities", [])
                if not isinstance(vulnerabilities, list) or len(vulnerabilities) > 10000:
                    return _emit(context, "osv", ScanStatus.ERROR, "OSV_BAD_VULNS")
                packages_seen += 1
                findings += len(vulnerabilities)
                if packages_seen > 20000 or findings > 100000:
                    return _emit(context, "osv", ScanStatus.ERROR, "OSV_RESULT_LIMIT")
        if packages_seen == 0 or (process.returncode == 1) != (findings > 0):
            return _emit(context, "osv", ScanStatus.ERROR, "OSV_INCOMPLETE_OR_EXIT_MISMATCH")
        if findings:
            return _emit(context, "osv", ScanStatus.FINDINGS,
                         "OFFLINE_VULNERABILITIES_REDACTED", findings)
        return _emit(context, "osv", ScanStatus.PASS, "OFFLINE_DEPENDENCY_SCAN_ONLY")
    except (OSError, ValueError, KeyError, UnicodeError, subprocess.TimeoutExpired):
        return _emit(context, "osv", ScanStatus.ERROR, "OSV_OFFLINE_UNAVAILABLE")

@dataclass(frozen=True)
class OfflineCacheInspection:
    """Read-only cache identity snapshot; no OSV scanner or package execution."""
    state: str
    actual_zip_sha256: str | None
    age_days: int | None
    may_install: bool = False
    may_execute_dependencies: bool = False
    independently_verified: bool = False

    def __post_init__(self) -> None:
        if (self.state not in {"CACHE_PIN_MATCH_STATIC_ONLY", "UNKNOWN_HOLD"}
            or any(getattr(self, flag) is not False for flag in (
                "may_install", "may_execute_dependencies", "independently_verified",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def inspect_osv_offline_cache(
    pin: OfflineDatabasePin, *, cache_root: str | Path,
    worktree: str | Path, original_checkout: str | Path,
) -> OfflineCacheInspection:
    """Read fixed-format OSV zip and compare hash/age without network access.

    A caller-controlled CheckedAt timestamp or SHA is NOT independent evidence;
    a protected owner verifier must supply these values for runtime trust.
    """
    if not isinstance(pin, OfflineDatabasePin):
        raise CodeShieldHold("UNPINNED_SCANNER")
    now = datetime.now(timezone.utc)
    age = (now - pin.checked_at_utc.astimezone(timezone.utc)).total_seconds() / 86400
    if age < 0 or age >= pin.maximum_age_days:
        return OfflineCacheInspection("UNKNOWN_HOLD", None, None)
    root = Path(cache_root)
    work, original = Path(worktree), Path(original_checkout)
    if (not root.is_absolute() or ".." in root.parts
        or not work.is_absolute() or not original.is_absolute()
        or any(root == path or root in path.parents or path in root.parents
               for path in (work, original))):
        return OfflineCacheInspection("UNKNOWN_HOLD", None, int(age))
    # Disallow a reparse/alias hop in any parent before reading a DB cache.
    for part in (root, *root.parents):
        try:
            info = part.lstat()
            if (not stat.S_ISDIR(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) &
                   getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                return OfflineCacheInspection("UNKNOWN_HOLD", None, int(age))
        except (OSError, ValueError):
            return OfflineCacheInspection("UNKNOWN_HOLD", None, int(age))
    file = root / "osv-scalibr" / pin.ecosystem / "all.zip"
    result = _file_sha(file, _MAX_BINARY)
    return OfflineCacheInspection(
        "CACHE_PIN_MATCH_STATIC_ONLY" if result == pin.zip_sha256
        else "UNKNOWN_HOLD",
        result, int(age),
    )
