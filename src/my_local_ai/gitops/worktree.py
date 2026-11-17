"""Non-executing worktree planning boundary.

Never invokes git worktree add, checkout, hooks, filter drivers or a model.
A separate protected OS runner must validate the actual Git commit, ignored
file inventory, active filters, worktree identity and F18 trust boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .path_guard import ScopePreflight, ScopeHold, preflight_paths
import re

_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


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
    if not isinstance(task_id, str) or _TASK_ID.fullmatch(task_id) is None:
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
import os as _os


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
        flags = (_os.O_RDONLY | getattr(_os, "O_NOFOLLOW", 0)
                 | getattr(_os, "O_BINARY", 0))
        fd = _os.open(path, flags)
        with _os.fdopen(fd, "rb") as f:
            opened = _os.fstat(f.fileno())
            if (not _stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_ino, opened.st_dev) != (before.st_ino, before.st_dev)):
                raise GitInventoryHold("UNSAFE_GIT_METADATA")
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


# Source-only lifecycle contract. The protected runner is intentionally absent:
# generating/validating these intents never creates or removes a Git worktree.
from hashlib import sha256 as _sha256
import json as _json


@_dataclass(frozen=True)
class WorktreeLifecyclePreview:
    task_id: str
    source_sha: str
    main_sha: str
    original_checkout: str
    disposable_worktree: str
    scope_sha256: str
    stage: str = "HOLD_PROTECTED_WORKTREE_LIFECYCLE_RUNNER"
    created: bool = False
    cleaned_up: bool = False
    original_modified: bool = False
    may_run_git: bool = False
    may_delete_paths: bool = False
    may_write_original: bool = False


@_dataclass(frozen=True)
class WorktreeCleanupPreview:
    task_id: str
    scope_sha256: str
    stage: str = "HOLD_PROTECTED_CLEANUP_RUNNER"
    cleanup_performed: bool = False
    may_delete_paths: bool = False
    may_update_main: bool = False


def plan_disposable_lifecycle(
    intent: WorktreeIntent, snapshot: GitInventorySnapshot,
) -> WorktreeLifecyclePreview:
    """Bind preflight, baseline and main-ref snapshot to a non-executable intent.

    Trusted OS owner must re-attest inode/reparse identities and read back exact
    Git HEAD/index/config immediately before any creation or cleanup. A guest
    supplied snapshot (or this digest) is not trusted evidence.
    """
    if not isinstance(intent, WorktreeIntent) or not isinstance(snapshot, GitInventorySnapshot):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    if (intent.state != "PLAN_ONLY_NO_GIT_EXECUTION"
        or intent.source_modified is not False
        or intent.trusted_reviewer_present is not False
        or not isinstance(intent.preflight, ScopePreflight)
        or intent.preflight.status != "PRECHECK_ONLY"
        or intent.preflight.writes_allowed is not False
        or intent.preflight.git_verified is not False
        or intent.preflight.reviewer_verified is not False):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    try:
        current = plan_disposable(
            task_id=intent.task_id, worktree=intent.preflight.worktree,
            original_checkout=intent.preflight.original_checkout,
            baseline_sha=intent.baseline_sha,
            allowed_paths=intent.preflight.allowed_paths,
        )
    except (ValueError, ScopeHold, OSError):
        raise GitInventoryHold("UNSAFE_GIT_PATH") from None
    if current != intent:
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    inspected = audit_disposable_git_inventory(intent, snapshot)
    if inspected.may_run_coder or inspected.may_write_worktree or inspected.may_update_git_ref:
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    identity = {
        "task_id": intent.task_id,
        "source_sha": inspected.source_sha,
        "main_sha": inspected.main_sha,
        "original": intent.preflight.original_checkout,
        "disposable": intent.preflight.worktree,
        "allowed_paths": intent.preflight.allowed_paths,
    }
    digest = _sha256(
        b"mla-worktree-lifecycle/v1|" + _json.dumps(
            identity, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    return WorktreeLifecyclePreview(
        intent.task_id, inspected.source_sha, inspected.main_sha,
        intent.preflight.original_checkout, intent.preflight.worktree, digest,
    )


def plan_disposable_cleanup(
    lifecycle: WorktreeLifecyclePreview, intent: WorktreeIntent,
    current_snapshot: GitInventorySnapshot,
) -> WorktreeCleanupPreview:
    """Only preview cleanup for a still-clean, exact-pinned disposable tree.

    Never delete a dirty checkout, unrelated directory, original or main.
    No OS/Git effects; real owner-controlled cleanup needs a new protected
    readback and separate runtime permission after F18/phase gates.
    """
    if (not isinstance(lifecycle, WorktreeLifecyclePreview)
        or lifecycle.stage != "HOLD_PROTECTED_WORKTREE_LIFECYCLE_RUNNER"
        or lifecycle.created is not False
        or lifecycle.cleaned_up is not False
        or lifecycle.original_modified is not False
        or lifecycle.may_run_git is not False
        or lifecycle.may_delete_paths is not False
        or lifecycle.may_write_original is not False):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    fresh = plan_disposable_lifecycle(intent, current_snapshot)
    if fresh != lifecycle:
        raise GitInventoryHold("STALE_GIT_SOURCE")
    return WorktreeCleanupPreview(lifecycle.task_id, lifecycle.scope_sha256)


# SWU-016: a real no-checkout Git worktree creation path for a future
# independently protected owner OS runner. OS_CHANGE grants are categorically
# rejected by the current v1 signer, so this route stays on hard runtime HOLD
# until an approved action-bound signer and F18 isolation exist.
@_dataclass(frozen=True)
class DisposableCreateReceipt:
    task_id: str
    baseline_sha: str
    disposable_path: str
    stage: str = "CREATED_NO_CHECKOUT_UNVERIFIED"
    created: bool = True
    checked_out_source: bool = False
    coder_permitted: bool = False
    reviewer_verified: bool = False
    may_integrate: bool = False
    may_publish: bool = False


def create_disposable_no_checkout(
    intent: WorktreeIntent, *, plan_sha256: str, owner_grant,
    trusted_hmac_key: bytes | None, trusted_live_consent_check,
    now_seconds: int, protected_git_call, protected_git_readback,
) -> DisposableCreateReceipt:
    """Create ONLY an empty detached linked worktree, never checkout files.

    Caller supplies a genuinely protected Git invoker/readback on the owner
    side; this function never provides one or accepts guest receipts as proof.
    The current v1 owner signer rejects OS_CHANGE: with today's policy this
    MUST raise before a Git operation. When explicitly authorized in a future
    separate High-approved trust layer, --no-checkout prevents filters/smudge
    and the post-readback must match source, main and original SHA exactly.
    """
    from my_local_ai.contracts.approval import authorize_claim
    from my_local_ai.gitops.path_guard import ScopeHold

    if (not isinstance(intent, WorktreeIntent)
        or intent.state != "PLAN_ONLY_NO_GIT_EXECUTION"
        or intent.source_modified is not False
        or intent.trusted_reviewer_present is not False
        or not isinstance(intent.preflight, ScopePreflight)
        or intent.preflight.writes_allowed is not False
        or intent.preflight.git_verified is not False
        or intent.preflight.reviewer_verified is not False
        or not isinstance(plan_sha256, str)
        or _re.fullmatch(r"[0-9a-f]{64}", plan_sha256) is None
        or type(now_seconds) is not int or now_seconds <= 0
        or not callable(protected_git_call)
        or not callable(protected_git_readback)):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    if not authorize_claim(
        owner_grant, trusted_hmac_key=trusted_hmac_key,
        expected_plan_sha=plan_sha256,
        expected_source_sha=intent.baseline_sha,
        required_scope="OS_CHANGE", now_seconds=now_seconds,
        trusted_live_consent_check=trusted_live_consent_check,
    ):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    # This block is deliberately unreachable with today's signer. It is real
    # creation source for the separately approved owner-runner integration,
    # not a command any untrusted worker/app is allowed to trigger.
    try:
        fresh = plan_disposable(
            task_id=intent.task_id, worktree=intent.preflight.worktree,
            original_checkout=intent.preflight.original_checkout,
            baseline_sha=intent.baseline_sha,
            allowed_paths=intent.preflight.allowed_paths,
        )
        if fresh != intent:
            raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
        work = _Path(intent.preflight.worktree)
        original = _Path(intent.preflight.original_checkout)
        if (not work.is_dir() or work.is_symlink()
            or any(work.iterdir()) or not (original / ".git").is_dir()):
            raise GitInventoryHold("UNSAFE_GIT_PATH")
        # No checkout: only owner-owned Git metadata changes. A failed call
        # leaves the worktree for a separately approved recovery, not deletion.
        argv = ("worktree", "add", "--detach", "--no-checkout", "--",
                str(work), intent.baseline_sha)
        result = protected_git_call(original, argv)
        if type(result) is not int or result != 0:
            raise GitInventoryHold("UNSAFE_GIT_METADATA")
        audit_linked_worktree_metadata(intent)
        snapshot = protected_git_readback(intent)
        verified = audit_disposable_git_inventory(intent, snapshot)
        if (verified.source_sha != intent.baseline_sha
            or verified.original_sha != intent.baseline_sha
            or verified.may_write_worktree or verified.may_update_git_ref):
            raise GitInventoryHold("STALE_GIT_SOURCE")
        files = set(work.iterdir())
        if files != {work / ".git"}:
            raise GitInventoryHold("DIRTY_DISPOSABLE")
        return DisposableCreateReceipt(
            intent.task_id, intent.baseline_sha, str(work),
        )
    except (ScopeHold, OSError, ValueError) as exc:
        if isinstance(exc, GitInventoryHold):
            raise
        raise GitInventoryHold("UNSAFE_GIT_METADATA") from None


# SWU-019: fixed-argv HEAD/index readback. This is data collection for a
# separately protected owner Git reader, NOT an F18 trusted review.
_MAX_GIT_READ_BYTES = 8 * 1024 * 1024


def _bounded_protected_git_read(reader, root: _Path, argv: tuple[str, ...],
                                *, max_bytes: int = _MAX_GIT_READ_BYTES) -> bytes:
    if not callable(reader) or not isinstance(root, _Path):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    try:
        value = reader(root, argv)
    except Exception:
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY") from None
    if not isinstance(value, bytes) or len(value) > max_bytes:
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    return value


def _read_protected_sha(reader, root: _Path, argv: tuple[str, ...]) -> str:
    raw = _bounded_protected_git_read(reader, root, argv, max_bytes=128)
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError:
        raise GitInventoryHold("STALE_GIT_SOURCE") from None
    if not _HEX40.fullmatch(value):
        raise GitInventoryHold("STALE_GIT_SOURCE")
    return value


def _check_protected_config_keys(reader, root: _Path) -> None:
    # Reject dangerous Git config before running status, which may otherwise
    # call fsmonitor or extension hooks. These keys are read by fixed argv only.
    raw = _bounded_protected_git_read(
        reader, root, ("config", "--name-only", "--null", "--list"),
        max_bytes=256 * 1024,
    )
    try:
        keys = raw.decode("utf-8").split("\0")
    except UnicodeDecodeError:
        raise GitInventoryHold("UNSAFE_GIT_METADATA") from None
    if keys and keys[-1] == "":
        keys.pop()
    if len(keys) > 4096:
        raise GitInventoryHold("UNSAFE_GIT_METADATA")
    blocked_exact = {
        "core.hookspath","core.worktree","core.fsmonitor",
        "core.attributesfile","core.sshcommand",
        "extensions.worktreeconfig",
    }
    blocked_prefixes = (
        "include.", "includeif.", "filter.", "diff.", "merge.",
        "submodule.", "credential.", "alias.",
    )
    if any(
        not key or len(key) > 200 or key != key.strip()
        or key.lower() in blocked_exact
        or key.lower().startswith(blocked_prefixes)
        for key in keys
    ):
        raise GitInventoryHold("UNSAFE_GIT_METADATA")


def read_protected_git_inventory(
    intent: WorktreeIntent, *, expected_main_sha: str,
    protected_git_read, no_checkout: bool = False,
) -> GitInventorySnapshot:
    """Read actual Git HEAD, main and stage-0 index via fixed read-only argv.

    The read callback is injected by an *owner-protected* environment; an
    untrusted guest callback does NOT make its output trustworthy. Missing
    tracked files in a deliberately empty --no-checkout worktree are accepted
    only after confirming they match every stage-0 index path; changes, unknown
    files, .git aliases, hooks/filters and config overrides are rejected.
    """
    if (not isinstance(intent, WorktreeIntent)
        or not isinstance(expected_main_sha, str)
        or _HEX40.fullmatch(expected_main_sha) is None
        or type(no_checkout) is not bool
        or not callable(protected_git_read)):
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
    try:
        fresh = plan_disposable(
            task_id=intent.task_id,
            worktree=intent.preflight.worktree,
            original_checkout=intent.preflight.original_checkout,
            baseline_sha=intent.baseline_sha,
            allowed_paths=intent.preflight.allowed_paths,
        )
        if fresh != intent:
            raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
        audit_linked_worktree_metadata(intent)
        work = _Path(intent.preflight.worktree)
        original = _Path(intent.preflight.original_checkout)
        if no_checkout and set(work.iterdir()) != {work / ".git"}:
            raise GitInventoryHold("DIRTY_DISPOSABLE")
        for directory in (original, work):
            _check_protected_config_keys(protected_git_read, directory)
        original_sha = _read_protected_sha(
            protected_git_read, original,
            ("rev-parse", "--verify", "HEAD^{commit}"),
        )
        main_sha = _read_protected_sha(
            protected_git_read, original,
            ("rev-parse", "--verify", "refs/heads/main^{commit}"),
        )
        disposable_sha = _read_protected_sha(
            protected_git_read, work,
            ("rev-parse", "--verify", "HEAD^{commit}"),
        )
        if (original_sha != intent.baseline_sha
            or main_sha != expected_main_sha
            or disposable_sha != intent.baseline_sha):
            raise GitInventoryHold("STALE_GIT_SOURCE")

        index_raw = _bounded_protected_git_read(
            protected_git_read, work, ("ls-files", "--stage", "-z"),
        )
        rows = index_raw.split(b"\0")
        if rows[-1] != b"":
            raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")
        entries = []
        for row in rows[:-1]:
            try:
                header, name = row.split(b"\t", 1)
                mode, sha, stage = header.decode("ascii").split(" ")
                path = name.decode("utf-8", "strict")
            except (UnicodeError, ValueError):
                raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY") from None
            if stage != "0":
                raise GitInventoryHold("UNSAFE_GIT_MODE")
            entries.append(IndexEntry(path, mode, sha))
            if len(entries) > _INVENTORY_PATH_LIMIT:
                raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY")

        status_raw = _bounded_protected_git_read(
            protected_git_read, work,
            ("status", "--porcelain=v1", "-z",
             "--untracked-files=all", "--ignored=matching"),
        )
        tracked_names = {entry.relative_path for entry in entries}
        if not no_checkout:
            if status_raw:
                raise GitInventoryHold("DIRTY_DISPOSABLE")
        else:
            status_rows = status_raw.split(b"\0")
            if status_rows[-1] != b"":
                raise GitInventoryHold("DIRTY_DISPOSABLE")
            missing = []
            for line in status_rows[:-1]:
                if not line.startswith(b" D "):
                    raise GitInventoryHold("DIRTY_DISPOSABLE")
                try:
                    missing.append(line[3:].decode("utf-8", "strict"))
                except UnicodeDecodeError:
                    raise GitInventoryHold("UNSAFE_GIT_PATH") from None
            if len(missing) != len(set(missing)) or set(missing) != tracked_names:
                raise GitInventoryHold("DIRTY_DISPOSABLE")
        # The caller may use this snapshot only as a bounded index/readback,
        # not an owner/F18 execution attestation.
        snapshot = GitInventorySnapshot(
            source_commit_sha=intent.baseline_sha,
            disposable_head_sha=disposable_sha,
            original_head_sha=original_sha,
            main_ref_sha=main_sha,
            expected_main_ref_sha=expected_main_sha,
            index_entries=tuple(entries),
        )
        audit_disposable_git_inventory(intent, snapshot)
        return snapshot
    except (OSError, ScopeHold, ValueError) as exc:
        if isinstance(exc, GitInventoryHold):
            raise
        raise GitInventoryHold("UNTRUSTED_GIT_INVENTORY") from None
