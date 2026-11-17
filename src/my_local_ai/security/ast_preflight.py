"""Read-only CodeShield Python AST and changed-path proposal preflight.

No generated module import, compilation to bytecode, test discovery or execution.
This scanner cannot establish filesystem/Git freshness, OS isolation or F18.
"""
from __future__ import annotations

import ast
import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Mapping

from my_local_ai.gitops.path_guard import preflight_paths, ScopeHold
from .codeshield_contracts import (
    CodeShieldContext, CodeShieldHold, RiskOutcome, checked_relative_path,
)

_MAX_SINGLE_BYTES = 256 * 1024
_MAX_TOTAL_BYTES = 1024 * 1024
_MAX_AST_NODES = 12000
_MAX_FINDINGS = 32

_DANGEROUS_MODULES = frozenset({
    "os", "sys", "subprocess", "shutil", "socket", "requests", "httpx",
    "urllib", "ftplib", "smtplib", "ctypes", "winreg", "importlib",
    "runpy", "pathlib", "pickle", "marshal", "multiprocessing", "pip",
})
_HIGH_CALLS = frozenset({
    "eval", "exec", "compile", "open", "__import__", "input",
    "os.remove", "os.unlink", "os.rmdir", "os.removedirs", "os.system",
    "os.popen", "shutil.rmtree", "shutil.move", "shutil.copytree",
    "pathlib.Path.unlink", "pathlib.Path.rmdir", "Path.unlink",
    "Path.rmdir", "subprocess.run", "subprocess.Popen", "subprocess.call",
    "subprocess.check_output", "subprocess.check_call",
    "builtins.exec", "builtins.eval",
})
_DYNAMIC_CALLS = frozenset({
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
    "execfile", "importlib.import_module", "runpy.run_module",
    "runpy.run_path", "os.getenv",
})
_SUSPICIOUS_METHODS = frozenset({
    "unlink", "rmdir", "rmtree", "remove", "system", "popen",
    "Popen", "run", "check_call", "check_output", "connect",
    "send", "sendall", "request", "urlopen", "download", "write_text",
    "write_bytes", "chmod", "chown", "replace", "rename",
    "execute", "executescript",
})


@dataclass(frozen=True)
class FileFinding:
    relative_path: str
    line: int
    code: str
    high_risk: bool = False

    def __post_init__(self) -> None:
        checked_relative_path(self.relative_path)
        if type(self.line) is not int or self.line < 1:
            raise CodeShieldHold()
        if not re.fullmatch(r"[A-Z_]{3,48}", self.code):
            raise CodeShieldHold()


@dataclass(frozen=True)
class ASTPreflight:
    context_sha256: str
    file_digests: tuple[tuple[str, str], ...]
    findings: tuple[FileFinding, ...]
    outcome: RiskOutcome
    reason: str
    imported_generated_modules: bool = False
    generated_code_executed: bool = False
    git_diff_verified: bool = False
    f18_independently_verified: bool = False
    may_execute: bool = False
    may_promote: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.outcome, RiskOutcome)
            or any(getattr(self, name) is not False for name in (
                "imported_generated_modules", "generated_code_executed",
                "git_diff_verified", "f18_independently_verified",
                "may_execute", "may_promote",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


@dataclass(frozen=True)
class ChangedPathPreflight:
    context_sha256: str
    changed_paths: tuple[str, ...]
    state: str = "READ_ONLY_SCOPE_PROPOSAL_UNVERIFIED_GIT_DIFF"
    git_diff_verified: bool = False
    reviewer_verified: bool = False
    may_write: bool = False
    may_execute: bool = False

    def __post_init__(self) -> None:
        if self.state != "READ_ONLY_SCOPE_PROPOSAL_UNVERIFIED_GIT_DIFF" or any(
            getattr(self, key) is not False for key in (
                "git_diff_verified", "reviewer_verified", "may_write", "may_execute"
            )
        ):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def preflight_changed_paths(
    context: CodeShieldContext, *, worktree: str | Path,
    original_checkout: str | Path, changed_paths: tuple[str, ...],
) -> ChangedPathPreflight:
    """Call existing lstat/reparse/alias guard; never trust claimed changed set.

    Protected-side Git reader must independently compare the exact baseline
    and candidate index, ignored/untracked paths, hooks/filters and ref SHA.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    if (not isinstance(changed_paths, tuple) or not 1 <= len(changed_paths) <= 16
        or len(set(changed_paths)) != len(changed_paths)):
        raise CodeShieldHold("UNSAFE_PATH")
    for name in changed_paths:
        checked_relative_path(name)
        if name not in context.allowed_paths:
            raise CodeShieldHold("UNSAFE_PATH")
    if tuple(sorted(changed_paths)) != changed_paths:
        raise CodeShieldHold("UNSAFE_PATH")
    try:
        scoped = preflight_paths(
            worktree=worktree, original_checkout=original_checkout,
            baseline_sha=context.source_git_sha, allowed_paths=changed_paths,
        )
    except ScopeHold:
        raise CodeShieldHold("UNSAFE_PATH") from None
    if (scoped.writes_allowed or scoped.git_verified or scoped.reviewer_verified
        or scoped.allowed_paths != changed_paths):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    return ChangedPathPreflight(context.fingerprint_sha256, changed_paths)


def _call_name(expr: ast.expr) -> str:
    parts: list[str] = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if isinstance(expr, ast.Name):
        parts.append(expr.id)
        return ".".join(reversed(parts))
    return ""


def scan_python_sources(
    context: CodeShieldContext, sources: Mapping[str, bytes | str],
) -> ASTPreflight:
    """Parse bounded in-memory source; suspicious/unknown always HOLD.

    The source hash here is sha256(content), not a verified Git tree object.
    Scanner success never means safe-to-execute, safe imports or safe tests.
    """
    if (not isinstance(context, CodeShieldContext)
        or not isinstance(sources, dict) or not 1 <= len(sources) <= 16):
        raise CodeShieldHold()
    if set(sources) - set(context.allowed_paths):
        raise CodeShieldHold("UNSAFE_PATH")
    findings: list[FileFinding] = []
    digests: list[tuple[str, str]] = []
    total_bytes = 0
    parse_failure = False
    high = False

    def add(path: str, line: int, code: str, *, severe: bool = False) -> None:
        nonlocal high
        high = high or severe
        if len(findings) < _MAX_FINDINGS:
            findings.append(FileFinding(path, max(1, line), code, severe))

    for path in sorted(sources):
        checked_relative_path(path)
        if not path.endswith(".py"):
            raise CodeShieldHold("UNSAFE_PATH")
        raw_value = sources[path]
        if isinstance(raw_value, bytes):
            raw = raw_value
        elif isinstance(raw_value, str):
            try:
                raw = raw_value.encode("utf-8")
            except UnicodeError:
                raw = b""
                parse_failure = True
        else:
            raise CodeShieldHold()
        total_bytes += len(raw)
        if (not raw or len(raw) > _MAX_SINGLE_BYTES
            or total_bytes > _MAX_TOTAL_BYTES or b"\x00" in raw):
            parse_failure = True
            add(path, 1, "SOURCE_SIZE_OR_ENCODING")
            continue
        digests.append((path, sha256(raw).hexdigest()))
        try:
            source_text = raw.decode("utf-8", errors="strict")
            tree = ast.parse(source_text, filename="<untrusted-source>", mode="exec")
        except (SyntaxError, UnicodeError, ValueError, RecursionError, MemoryError):
            parse_failure = True
            add(path, 1, "SYNTAX_OR_PARSE_ERROR")
            continue
        nodes = 0
        try:
            for node in ast.walk(tree):
                nodes += 1
                if nodes > _MAX_AST_NODES:
                    parse_failure = True
                    add(path, 1, "AST_NODE_LIMIT")
                    break
                line = getattr(node, "lineno", 1)
                if isinstance(node, ast.Import):
                    if any(alias.name.split(".", 1)[0] in _DANGEROUS_MODULES
                           for alias in node.names):
                        add(path, line, "SENSITIVE_IMPORT")
                elif isinstance(node, ast.ImportFrom):
                    if (node.level or node.module is None
                        or node.module.split(".", 1)[0] in _DANGEROUS_MODULES):
                        add(path, line, "SENSITIVE_IMPORT")
                elif isinstance(node, ast.Call):
                    name = _call_name(node.func)
                    last = name.rsplit(".", 1)[-1]
                    if name in _HIGH_CALLS or last in _SUSPICIOUS_METHODS:
                        add(path, line, "DANGEROUS_CALL", severe=True)
                    elif name in _DYNAMIC_CALLS or last in {
                        "__import__", "getattr", "setattr", "delattr"
                    }:
                        add(path, line, "DYNAMIC_DISPATCH", severe=True)
                elif isinstance(node, (ast.Delete, ast.Global, ast.Nonlocal)):
                    add(path, line, "MUTATION_OR_DYNAMIC_SCOPE", severe=True)
        except (RecursionError, MemoryError):
            parse_failure = True
            add(path, 1, "AST_RESOURCE_LIMIT")
    if parse_failure:
        outcome, reason = RiskOutcome.UNKNOWN_HOLD, "PARSER_OR_RESOURCE_HOLD"
    elif high:
        outcome, reason = RiskOutcome.HOLD_HIGH_RISK, "DANGEROUS_STATIC_PATTERN"
    elif findings:
        outcome, reason = RiskOutcome.REQUIRES_ISOLATION_HOLD, "SENSITIVE_STATIC_PATTERN"
    else:
        outcome, reason = RiskOutcome.ALLOW_NON_EXECUTING, "AST_STATIC_ONLY"
    return ASTPreflight(
        context.fingerprint_sha256, tuple(digests), tuple(findings),
        outcome, reason,
    )

def _read_scoped_python_file(path: Path) -> bytes:
    """Bounded lstat/open/fstat/readback of an untrusted file; never imports it."""
    try:
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or getattr(before, "st_file_attributes", 0) &
               getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or not 1 <= before.st_size <= _MAX_SINGLE_BYTES):
            raise CodeShieldHold("UNSAFE_PATH")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or opened.st_size != before.st_size):
                raise CodeShieldHold("STALE_EVIDENCE")
            data = handle.read(_MAX_SINGLE_BYTES + 1)
            current = os.fstat(handle.fileno())
        after = path.lstat()
        first = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if (len(data) != before.st_size
            or first != (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
            or first != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise CodeShieldHold("STALE_EVIDENCE")
        return data
    except CodeShieldHold:
        raise
    except (OSError, ValueError, OverflowError):
        raise CodeShieldHold("UNSAFE_PATH") from None


def scan_scoped_python_sources(
    context: CodeShieldContext, *, worktree: str | Path,
    original_checkout: str | Path, changed_paths: tuple[str, ...],
) -> ASTPreflight:
    """Read actual scoped files and parse them without executing untrusted code.

    This is the non-executing changed-path->AST caller link for CS-SWU-003.
    Caller still needs a protected Git reader to establish genuine changed paths
    and candidate SHA. A static ALLOW here is never a trust or runtime grant.
    """
    scope = preflight_changed_paths(
        context, worktree=worktree, original_checkout=original_checkout,
        changed_paths=changed_paths,
    )
    if (scope.git_diff_verified or scope.may_write or scope.may_execute
        or any(not path.endswith(".py") for path in changed_paths)):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    root = Path(worktree)
    content = {name: _read_scoped_python_file(root / name) for name in changed_paths}
    result = scan_python_sources(context, content)
    if (result.git_diff_verified or result.may_execute or result.may_promote):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    # Detect a changed file between the first read and AST conclusion.
    for name, digest in result.file_digests:
        if sha256(_read_scoped_python_file(root / name)).hexdigest() != digest:
            raise CodeShieldHold("STALE_EVIDENCE")
    if len(result.file_digests) != len(changed_paths):
        raise CodeShieldHold("STALE_EVIDENCE")
    return result
