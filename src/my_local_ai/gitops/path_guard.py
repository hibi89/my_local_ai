"""Fail-closed, read-only path preflight for a disposable Git worktree.

Not a Git worktree creator, Git hooks/filter/ignore check, sandbox, or F18
approval. No source modifications and no subprocess calls occur here.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
from typing import Iterable

from my_local_ai.contracts.task import safe_path

_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_GIT_META = {".git", ".gitignore", ".gitattributes", ".gitmodules", ".mailmap"}
_SECRET_PREFIX = (".env", ".ssh", ".aws", ".config", ".npmrc", ".pypirc")


class ScopeHold(ValueError):
    def __init__(self, reason: str = "UNSAFE_SCOPE"):
        self.code = reason if reason in {
            "UNSAFE_SCOPE", "UNSAFE_ORIGINAL", "UNSAFE_LINK",
            "PROTECTED_METADATA", "NONREGULAR", "UNSAFE_ALIAS",
            "UNSAFE_SOURCE", "MISSING_PARENT",
        } else "UNSAFE_SCOPE"
        super().__init__(self.code)


@dataclass(frozen=True)
class ScopePreflight:
    worktree: str
    original_checkout: str
    baseline_sha: str
    allowed_paths: tuple[str, ...]
    status: str = "PRECHECK_ONLY"
    writes_allowed: bool = False
    git_verified: bool = False
    reviewer_verified: bool = False


def _safe_segment(path: Path, *, directory: bool) -> None:
    try:
        info = path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        raise ScopeHold("MISSING_PARENT") from None
    if (stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & _REPARSE):
        raise ScopeHold("UNSAFE_LINK")
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ScopeHold("NONREGULAR")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ScopeHold("NONREGULAR")


def _safe_ancestors(path: Path) -> None:
    for part in reversed((path, *path.parents)):
        _safe_segment(part, directory=True)


def _disallow_metadata(relative: str) -> None:
    for segment in relative.split("/"):
        normalized = segment.casefold()
        if normalized in _GIT_META or normalized.startswith(_SECRET_PREFIX):
            raise ScopeHold("PROTECTED_METADATA")


def _check_disk_alias(parent: Path, segment: str) -> None:
    """Disallow alternate casing and Unicode variants of an existing child."""
    try:
        names = [name for name in os.listdir(parent) if name.casefold() == segment.casefold()]
    except (OSError, UnicodeError):
        raise ScopeHold("UNSAFE_ALIAS") from None
    if names and (len(names) != 1 or names[0] != segment):
        raise ScopeHold("UNSAFE_ALIAS")


def preflight_paths(
    *, worktree: str | Path, original_checkout: str | Path,
    baseline_sha: str, allowed_paths: Iterable[str],
) -> ScopePreflight:
    """Read-only preflight; caller must separately attest exact Git inventory.

    Fail-closed for symlinks/reparse/ADSes, filesystem aliases, hardlinks,
    missing intermediate directories, metadata and original overlap.
    """
    if not isinstance(baseline_sha, str) or not _GIT_SHA.fullmatch(baseline_sha):
        raise ScopeHold("UNSAFE_SOURCE")
    if isinstance(worktree, (str, Path)) and isinstance(original_checkout, (str, Path)):
        work = Path(worktree)
        original = Path(original_checkout)
    else:
        raise ScopeHold()
    if not work.is_absolute() or not original.is_absolute():
        raise ScopeHold()
    try:
        _safe_ancestors(work)
        _safe_ancestors(original)
    except (OSError, ValueError) as exc:
        if isinstance(exc, ScopeHold):
            raise
        raise ScopeHold() from None
    if work == original or work in original.parents or original in work.parents:
        raise ScopeHold("UNSAFE_ORIGINAL")
    paths = tuple(allowed_paths)
    if not 1 <= len(paths) <= 16:
        raise ScopeHold()
    normalized: list[str] = []
    for relative in paths:
        try:
            safe_path(relative)
        except ValueError:
            raise ScopeHold() from None
        _disallow_metadata(relative)
        if relative.casefold() in {p.casefold() for p in normalized}:
            raise ScopeHold("UNSAFE_ALIAS")
        current = work
        segments = relative.split("/")
        for segment in segments[:-1]:
            _check_disk_alias(current, segment)
            current = current / segment
            _safe_segment(current, directory=True)
        target = current / segments[-1]
        _check_disk_alias(current, segments[-1])
        try:
            target.lstat()
        except FileNotFoundError:
            pass  # only this final file may be new
        except OSError:
            raise ScopeHold() from None
        else:
            _safe_segment(target, directory=False)
        normalized.append(relative)
    # Paths and baseline only: no operation can use this as an execution grant.
    return ScopePreflight(
        str(work), str(original), baseline_sha, tuple(sorted(normalized)),
    )
