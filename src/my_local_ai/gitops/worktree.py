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
