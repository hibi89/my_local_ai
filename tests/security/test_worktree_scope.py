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


if __name__ == "__main__":
    unittest.main()
