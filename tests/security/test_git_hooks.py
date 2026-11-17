"""Synthetic source-tree hook/filter/metadata denial, no git invocation."""
import os
from pathlib import Path
import tempfile
import unittest

from my_local_ai.gitops.path_guard import ScopeHold,preflight_paths

SHA="a"*40


class GitMetadataGuardTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.original=self.root/"original"
        self.guest=self.root/"guest"
        for p in (self.original,self.guest):
            p.mkdir()
            (p/"src").mkdir()
            (p/".git").mkdir()
            (p/".git"/"hooks").mkdir()
        (self.original/"src"/"safe.py").write_text("x",encoding="utf-8")

    def preflight(self,path):
        return preflight_paths(worktree=self.guest,original_checkout=self.original,
                               baseline_sha=SHA,allowed_paths=(path,))

    def test_git_hooks_and_filter_files_never_editable(self):
        for filename in (
            ".git/hooks/pre-commit",
            ".git/config", ".git/HEAD",
            ".gitattributes",".gitignore",".gitmodules",
            "src/.gitattributes","src/.git/config",
            ".env", ".env.production", "src/.ssh/id_rsa",
            "src/.npmrc","src/.pypirc",
        ):
            with self.subTest(filename=filename),self.assertRaises(ScopeHold):
                self.preflight(filename)

    def test_symlink_escape_into_original_denied(self):
        escape=self.guest/"src"/"link.py"
        try:
            escape.symlink_to(self.original/"src"/"safe.py")
        except OSError:
            self.skipTest("symlink not available on runner")
        with self.assertRaises(ScopeHold):
            self.preflight("src/link.py")

    def test_hardlink_alias_to_original_denied(self):
        borrowed=self.guest/"src"/"borrowed.py"
        try:
            os.link(self.original/"src"/"safe.py",borrowed)
        except OSError:
            self.skipTest("hardlink unsupported")
        with self.assertRaises(ScopeHold):
            self.preflight("src/borrowed.py")
        self.assertEqual((self.original/"src"/"safe.py").read_text(encoding="utf-8"),"x")

    def test_preflight_does_not_create_git_ref_or_change_files(self):
        before=list((self.guest/"src").iterdir())
        result=self.preflight("src/new.py")
        self.assertEqual(result.status,"PRECHECK_ONLY")
        self.assertFalse(result.writes_allowed)
        self.assertFalse(result.git_verified)
        self.assertEqual(list((self.guest/"src").iterdir()),before)


if __name__=="__main__":
    unittest.main()



class NestedPathAliasDenialTests(GitMetadataGuardTests):
    def test_alias_of_original_via_parent_lexical_traversal_is_denied(self):
        with self.assertRaises(ScopeHold):
            preflight_paths(
                worktree=self.guest / ".." / "original",
                original_checkout=self.original,
                baseline_sha=SHA,
                allowed_paths=("src/safe.py",),
            )

    def test_scoped_generator_cannot_exhaust_memory_or_hang(self):
        count=[]
        def infinite():
            while True:
                count.append(1)
                yield "src/new.py"
        with self.assertRaises(ScopeHold):
            preflight_paths(
                worktree=self.guest,
                original_checkout=self.original,
                baseline_sha=SHA,
                allowed_paths=infinite(),
            )
        self.assertEqual(len(count),17)
