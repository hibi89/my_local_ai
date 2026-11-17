"""Pure defensive FS preflight on synthetic disposable folders; no git operations."""
import os
from pathlib import Path
import tempfile
import unittest

from my_local_ai.gitops.path_guard import ScopeHold, preflight_paths
from my_local_ai.gitops.worktree import plan_disposable

SHA = "a" * 40


class ScopePreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.original = self.root / "original"
        self.worktree = self.root / "disposable"
        for parent in (self.original, self.worktree):
            parent.mkdir()
            (parent / "src").mkdir()

    def inspect(self, paths=("src/main.py",)):
        return preflight_paths(worktree=self.worktree, original_checkout=self.original,
                               baseline_sha=SHA, allowed_paths=paths)

    def test_new_file_preflight_never_grants_writes_or_git_pass(self):
        result = self.inspect()
        self.assertEqual(result.allowed_paths, ("src/main.py",))
        self.assertEqual(result.status, "PRECHECK_ONLY")
        self.assertFalse(result.writes_allowed)
        self.assertFalse(result.git_verified)
        self.assertFalse(result.reviewer_verified)
        self.assertFalse((self.worktree / "src/main.py").exists())

    def test_worktree_plan_has_no_git_execution_or_mutation(self):
        request = plan_disposable(task_id="TASK-014",
                                  worktree=self.worktree, original_checkout=self.original,
                                  baseline_sha=SHA, allowed_paths=("src/main.py",))
        self.assertEqual(request.state, "PLAN_ONLY_NO_GIT_EXECUTION")
        self.assertFalse(request.source_modified)
        self.assertFalse(request.trusted_reviewer_present)
        self.assertEqual(list(self.worktree.iterdir()), [self.worktree / "src"])

    def test_existing_unique_regular_file_and_sibling_is_allowed_for_preflight(self):
        (self.worktree / "src" / "known.py").write_text("safe", encoding="utf-8")
        result = self.inspect(("src/known.py", "src/main.py"))
        self.assertEqual(result.allowed_paths, ("src/known.py", "src/main.py"))

    def test_original_or_nested_worktree_refused(self):
        for checkout in (self.original, self.root):
            with self.subTest(checkout=checkout), self.assertRaises(ScopeHold):
                preflight_paths(worktree=checkout, original_checkout=self.original,
                                baseline_sha=SHA, allowed_paths=("src/main.py",))
        child = self.original / "child"
        child.mkdir()
        with self.assertRaises(ScopeHold):
            preflight_paths(worktree=child, original_checkout=self.original,
                            baseline_sha=SHA, allowed_paths=("src/main.py",))

    def test_protected_metadata_and_ads_refused(self):
        bad = (".git/config", ".gitattributes", "src/.gitmodules", ".env",
               "src/.env.private", "src/secrets:stream", "src/../secret",
               "src/*.py", "src/CON", "/tmp/file")
        for rel in bad:
            with self.subTest(path=rel), self.assertRaises(ScopeHold):
                self.inspect((rel,))

    def test_different_case_and_duplicate_paths_refused(self):
        (self.worktree / "src/Real.py").write_text("safe", encoding="utf-8")
        with self.assertRaises(ScopeHold):
            self.inspect(("src/real.py",))
        with self.assertRaises(ScopeHold):
            self.inspect(("src/a.py", "src/A.py"))

    def test_missing_parent_refused(self):
        with self.assertRaises(ScopeHold):
            self.inspect(("missing/child.py",))

    def test_symlinked_file_and_parent_refused(self):
        sym = self.worktree / "src/escape.py"
        try:
            sym.symlink_to(self.original / "src" / "main.py")
        except OSError:
            self.skipTest("symlink privileges unavailable")
        with self.assertRaises(ScopeHold):
            self.inspect(("src/escape.py",))
        alias = self.worktree / "shortcut"
        alias.symlink_to(self.original / "src", target_is_directory=True)
        with self.assertRaises(ScopeHold):
            self.inspect(("shortcut/new.py",))

    def test_hardlink_refused(self):
        original = self.original / "src/owned.py"
        original.write_text("private", encoding="utf-8")
        linked = self.worktree / "src/linked.py"
        try:
            os.link(original, linked)
        except OSError:
            self.skipTest("hardlinks not supported")
        with self.assertRaises(ScopeHold):
            self.inspect(("src/linked.py",))
        self.assertEqual(original.read_text(encoding="utf-8"), "private")

    def test_wrong_sha_or_nonexistent_worktree_fails(self):
        with self.assertRaises(ScopeHold):
            preflight_paths(worktree=self.worktree, original_checkout=self.original,
                            baseline_sha="bad", allowed_paths=("src/file.py",))
        with self.assertRaises(ScopeHold):
            preflight_paths(worktree=self.worktree / "missing", original_checkout=self.original,
                            baseline_sha=SHA, allowed_paths=("src/file.py",))


# Synthetic inventory of an existing, freshly materialized disposable checkout.
from my_local_ai.gitops.worktree import (
    IndexEntry, GitInventorySnapshot, GitInventoryHold,
    audit_disposable_git_inventory,
)
from dataclasses import replace


class TrackedGitMetadataTests(ScopePreflightTests):
    def make_intent(self):
        return plan_disposable(
            task_id="TASK-014", worktree=self.worktree,
            original_checkout=self.original, baseline_sha=SHA,
            allowed_paths=("src/main.py",),
        )

    def inventory(self, **updates):
        values = {
            "source_commit_sha": SHA,
            "disposable_head_sha": SHA,
            "original_head_sha": SHA,
            "main_ref_sha": "b"*40,
            "expected_main_ref_sha": "b"*40,
            "index_entries": (IndexEntry("src/main.py", "100644", "c"*40),),
        }
        values.update(updates)
        return GitInventorySnapshot(**values)

    def test_clean_inventory_checks_source_and_stays_nonexecuting(self):
        v = audit_disposable_git_inventory(self.make_intent(), self.inventory())
        self.assertEqual(v.tracked_files, 1)
        self.assertEqual(v.allowed_paths_present, ("src/main.py",))
        self.assertFalse(v.may_run_coder)
        self.assertFalse(v.may_write_worktree)
        self.assertFalse(v.may_update_git_ref)

    def test_original_main_or_disposable_ref_race_is_hold(self):
        for bad in (
            {"source_commit_sha": "f"*40},
            {"disposable_head_sha": "f"*40},
            {"original_head_sha": "f"*40},
            {"main_ref_sha": "f"*40},
            {"expected_main_ref_sha": "invalid"},
        ):
            with self.subTest(bad=bad), self.assertRaises(GitInventoryHold):
                audit_disposable_git_inventory(self.make_intent(), self.inventory(**bad))

    def test_git_hook_filters_and_unsafe_git_config_fail_shut(self):
        for bad in (
            {"custom_hooks_path": ".git/hooks"},
            {"config_has_include": True},
            {"core_worktree_overridden": True},
            {"detected_submodules": True},
            {"attributes_untrusted": True},
            {"active_filter_names": ("credential-helper",)},
        ):
            with self.subTest(bad=bad), self.assertRaises(GitInventoryHold):
                audit_disposable_git_inventory(self.make_intent(), self.inventory(**bad))

    def test_dirty_ignored_untracked_or_staged_checkout_hold(self):
        for bad in (
            {"dirty_paths": ("src/main.py",)},
            {"untracked_paths": (".env",)},
            {"ignored_paths": ("ignored/private.txt",)},
        ):
            with self.subTest(bad=bad), self.assertRaises(GitInventoryHold):
                audit_disposable_git_inventory(self.make_intent(), self.inventory(**bad))

    def test_tracked_symlink_submodule_meta_git_and_alias_blocked(self):
        for entry in (
            IndexEntry("src/main.py", "120000", "c"*40),
            IndexEntry("src/vendor", "160000", "c"*40),
            IndexEntry(".gitmodules", "100644", "c"*40),
            IndexEntry(".gitattributes", "100644", "c"*40),
            IndexEntry("src/.git/config", "100644", "c"*40),
            IndexEntry("../secret", "100644", "c"*40),
        ):
            with self.subTest(entry=entry), self.assertRaises(GitInventoryHold):
                audit_disposable_git_inventory(self.make_intent(), self.inventory(index_entries=(entry,)))

    def test_casefold_index_collision_and_duplicate_entry_denied(self):
        entries = (
            IndexEntry("src/main.py", "100644", "c"*40),
            IndexEntry("src/MAIN.py", "100644", "d"*40),
        )
        with self.assertRaises(GitInventoryHold):
            audit_disposable_git_inventory(self.make_intent(), self.inventory(index_entries=entries))


if __name__ == "__main__":
    unittest.main()
