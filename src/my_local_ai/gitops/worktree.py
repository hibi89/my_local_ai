"""Non-executing worktree planning boundary.

Never invokes git worktree add, checkout, hooks, filter drivers or a model.
A separate protected OS runner must validate the actual Git commit, ignored
file inventory, active filters, worktree identity and F18 trust boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .path_guard import ScopePreflight, preflight_paths


@dataclass(frozen=True)
class WorktreeIntent:
    task_id: str
    baseline_sha: str
    preflight: ScopePreflight
    state: str = "PLAN_ONLY_NO_GIT_EXECUTION"
    source_modified: bool = False
    trusted_reviewer_present: bool = False


def plan_disposable(
    *, task_id: str, worktree: str | Path,
    original_checkout: str | Path, baseline_sha: str,
    allowed_paths: tuple[str, ...],
) -> WorktreeIntent:
    if not isinstance(task_id, str) or not task_id.isascii() or not (3 <= len(task_id) <= 64):
        raise ValueError("invalid task ID")
    checked = preflight_paths(
        worktree=worktree, original_checkout=original_checkout,
        baseline_sha=baseline_sha, allowed_paths=allowed_paths,
    )
    return WorktreeIntent(task_id, baseline_sha, checked)


# The *protected* Git reader supplies this bounded snapshot after creating
# its isolated checkout. Caller-provided JSON/guest Git output is NOT a proof of
# OS isolation; this contract rejects unsafe inventories but never authorizes
# a write, checker launch, or ref update by itself.
from dataclasses import dataclass as _dataclass
import re as _re

_HEX40 = _re.compile(r"[0-9a-f]{40}\Z")
_INVENTORY_PATH_LIMIT = 16384
_ALLOWED_MODES = frozenset({"100644", "100755"})
_BLOCKED_ATTRIBUTE_MARKERS = frozenset({
    "filter", "textconv", "working-tree-encoding", "diff", "merge",
    "export-subst", "ident",
})


class GitInventoryHold(ValueError):
    def __init__(self, code: str):
        self.code = code if code in {
            "STALE_GIT_SOURCE", "DIRTY_DISPOSABLE", "UNSAFE_GIT_METADATA",
            "UNSAFE_GIT_PATH", "UNTRUSTED_GIT_INVENTORY", "UNSAFE_GIT_MODE",
        } else "UNTRUSTED_GIT_INVENTORY"
        super().__init__(self.code)


@_dataclass(frozen=True)
class IndexEntry:
    relative_path: str
    mode: str
    object_sha: str


@_dataclass(frozen=True)
class GitInventorySnapshot:
    """Values obtained by trusted Git reader, not a guest-created receipt.

    The initial disposable checkout must have a clean index and worktree.
    Git filters, hooks, submodules and ignored/untracked files are held.
    """
    source_commit_sha: str
    disposable_head_sha: str
    original_head_sha: str
    main_ref_sha: str
    expected_main_ref_sha: str
    index_entries: tuple[IndexEntry, ...]
    dirty_paths: tuple[str, ...] = ()
    untracked_paths: tuple[str, ...] = ()
    ignored_paths: tuple[str, ...] = ()
    active_filter_names: tuple[str, ...] = ()
    custom_hooks_path: str | None = None
    config_has_include: bool = False
    core_worktree_overridden: bool = False
    detected_submodules: bool = False
    attributes_untrusted: bool = False


@_dataclass(frozen=True)
class InventoryPreflight:
    source_sha: str
    original_sha: str
    main_sha: str
    tracked_files: int
    allowed_paths_present: tuple[str, ...]
    state: str = "READ_ONLY_INVENTORY_PRECHECK_F18_NOT_PROVEN"
    may_run_coder: bool = False
    may_write_worktree: bool = False
    may_update_git_ref: bool = False


def audit_disposable_git_inventory(
    intent: WorktreeIntent, snapshot: GitInventorySnapshot,
) -> InventoryPreflight:
    """Read-only content/metadata safety check, never a trust-root grant.

    A separately protected Git reader MUST pin current ref readbacks, index,
    ignored/untracked paths, hooks, attributes and OS directory identity.
    This function explicitly cannot infer independence from a snapshot alone.
    """
    from my_local_ai.contracts.task import safe_path

    if not isinstance(intent, WorktreeIntent) or not isinstance(snapshot, GitInventorySnapshot):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    for digest in (
        snapshot.source_commit_sha, snapshot.disposable_head_sha,
        snapshot.original_head_sha, snapshot.main_ref_sha,
        snapshot.expected_main_ref_sha, intent.baseline_sha,
    ):
        if not isinstance(digest, str) or not _HEX40.fullmatch(digest):
            raise GitInventoryHold("STALE_GIT_SOURCE")
    if (intent.baseline_sha != snapshot.source_commit_sha
        or snapshot.disposable_head_sha != snapshot.source_commit_sha
        or snapshot.original_head_sha != snapshot.source_commit_sha
        or snapshot.main_ref_sha != snapshot.expected_main_ref_sha):
        raise GitInventoryHold("STALE_GIT_SOURCE")
    if (snapshot.custom_hooks_path is not None or snapshot.config_has_include is not False
        or snapshot.core_worktree_overridden is not False
        or snapshot.detected_submodules is not False
        or snapshot.attributes_untrusted is not False
        or snapshot.active_filter_names):
        raise GitInventoryHold("UNSAFE_GIT_METADATA")
    if (not isinstance(snapshot.index_entries, tuple)
        or len(snapshot.index_entries) > _INVENTORY_PATH_LIMIT
        or any(not isinstance(v, tuple) for v in (
            snapshot.dirty_paths, snapshot.untracked_paths, snapshot.ignored_paths,
            snapshot.active_filter_names
        ))):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    if snapshot.dirty_paths or snapshot.untracked_paths or snapshot.ignored_paths:
        raise GitInventoryHold("DIRTY_DISPOSABLE")
    seen: set[str] = set()
    tracked: set[str] = set()
    for entry in snapshot.index_entries:
        if not isinstance(entry, IndexEntry):
            raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
        try:
            p = safe_path(entry.relative_path)
        except ValueError:
            raise GitInventoryHold("UNSAFE_GIT_PATH") from None
        if (p.casefold() in seen or p.startswith(".git")
            or any(part.casefold() in (".gitattributes", ".gitmodules")
                   for part in p.split("/"))):
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        if entry.mode not in _ALLOWED_MODES:
            # Git 120000 symlink / 160000 submodule / unknown modes fail shut.
            raise GitInventoryHold("UNSAFE_GIT_MODE")
        if not isinstance(entry.object_sha, str) or not _HEX40.fullmatch(entry.object_sha):
            raise GitInventoryHold("UNSAFE_GIT_MODE")
        seen.add(p.casefold())
        tracked.add(p)
    # A path absent from the baseline can be added later, but no nested
    # symlinks/reparse/ignored aliases are permitted (path_guard checks FS).
    return InventoryPreflight(
        snapshot.source_commit_sha,
        snapshot.original_head_sha,
        snapshot.main_ref_sha,
        len(tracked),
        tuple(sorted(set(intent.preflight.allowed_paths) & tracked)),
    )


# Linked Git worktrees use .git *files*, pointing to an owner checkout's
# .git/worktrees/<id> metadata. Compare both directions after lstat.
# This read-only check is not OS isolation and cannot authorize integration.
from pathlib import Path as _Path
import stat as _stat


@_dataclass(frozen=True)
class LinkedGitdirPreflight:
    worktree_gitfile: str
    original_worktrees_root: str
    status: str = "READ_ONLY_LINK_MATCHED_NOT_OS_PROVEN"
    independent_f18_verified: bool = False
    may_write_git: bool = False


def _read_unique_metadata(path: _Path, *, max_bytes: int = 4096) -> str:
    try:
        before = path.lstat()
        if (not _stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or getattr(before, "st_file_attributes", 0)
            & getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or before.st_size > max_bytes):
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        with path.open("rb") as f:
            raw = f.read(max_bytes + 1)
        after = path.lstat()
        if (len(raw) > max_bytes or before.st_ino != after.st_ino
            or before.st_dev != after.st_dev or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns):
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        return raw.decode("utf-8").strip()
    except (UnicodeError, OSError):
        raise GitInventoryHold("UNSAFE_GIT_METADATA") from None


def audit_linked_worktree_metadata(intent: WorktreeIntent) -> LinkedGitdirPreflight:
    """Require a bidirectional Gitdir file match under the known original.

    A protected owner runner MUST re-check this immediately before work, along
    with Git HEAD/index/ignored/filter inventory and OS ACLs. Do not promote.
    """
    if not isinstance(intent, WorktreeIntent):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    work = _Path(intent.preflight.worktree)
    original = _Path(intent.preflight.original_checkout)
    root = original / ".git" / "worktrees"
    marker = work / ".git"
    # All paths must be resolved only after checking parent symlink/reparse.
    try:
        for folder in (original/".git", root,work, original):
            st=folder.lstat()
            if (not _stat.S_ISDIR(st.st_mode)
                or _stat.S_ISLNK(st.st_mode)
                or getattr(st, "st_file_attributes", 0)
                & getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise GitInventoryHold("UNSAFE_GIT_METADATA")
        link = _read_unique_metadata(marker)
        if not link.startswith("gitdir: "):
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        target=_Path(link[8:])
        if not target.is_absolute() or target == root:
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        # Prevent symlink/reparse escapes, including path traversal.
        if target.parent != root or target.name in ("", ".", ".."):
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        st=target.lstat()
        if (not _stat.S_ISDIR(st.st_mode) or _stat.S_ISLNK(st.st_mode)
            or getattr(st, "st_file_attributes", 0)
            & getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        back=_read_unique_metadata(target/"gitdir")
        if back != str(marker):
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        return LinkedGitdirPreflight(str(marker),str(root))
    except (OSError, ValueError) as exc:
        if isinstance(exc, GitInventoryHold):
            raise
        raise GitInventoryHold("UNSAFE_GIT_METADATA") from None
