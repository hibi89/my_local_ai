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

    def test_lifecycle_and_cleanup_intents_do_not_run_git(self):
        from my_local_ai.gitops.worktree import plan_disposable_lifecycle,plan_disposable_cleanup
        intent=self.make_intent()
        snapshot=self.inventory()
        started=plan_disposable_lifecycle(intent,snapshot)
        cleaned=plan_disposable_cleanup(started,intent,snapshot)
        self.assertEqual(len(started.scope_sha256),64)
        self.assertEqual(started.stage,"HOLD_PROTECTED_WORKTREE_LIFECYCLE_RUNNER")
        self.assertFalse(started.may_run_git)
        self.assertFalse(started.may_write_original)
        self.assertFalse(cleaned.cleanup_performed)
        self.assertFalse(cleaned.may_delete_paths)
        self.assertEqual(sorted(x.name for x in self.worktree.iterdir()),["src"])

    def test_lifecycle_snapshot_and_cleanup_races_fail_shut(self):
        from my_local_ai.gitops.worktree import plan_disposable_lifecycle,plan_disposable_cleanup
        intent=self.make_intent()
        accepted=plan_disposable_lifecycle(intent,self.inventory())
        for changed in (
            self.inventory(main_ref_sha="e"*40),
            self.inventory(original_head_sha="f"*40),
            self.inventory(dirty_paths=("src/main.py",)),
            self.inventory(ignored_paths=(".env",)),
        ):
            with self.subTest(changed=changed),self.assertRaises(GitInventoryHold):
                plan_disposable_cleanup(accepted,intent,changed)
        with self.assertRaises(GitInventoryHold):
            plan_disposable_cleanup(replace(accepted,may_delete_paths=True),intent,self.inventory())
        with self.assertRaises(GitInventoryHold):
            plan_disposable_cleanup(replace(accepted,disposable_worktree=str(self.original)),intent,self.inventory())

    def test_forged_lifecycle_flags_and_scope_are_refused(self):
        from my_local_ai.gitops.worktree import plan_disposable_lifecycle
        intent=self.make_intent()
        with self.assertRaises(GitInventoryHold):
            plan_disposable_lifecycle(replace(intent,source_modified=True),self.inventory())
        with self.assertRaises(GitInventoryHold):
            plan_disposable_lifecycle(replace(intent,baseline_sha="f"*40),self.inventory())
        with self.assertRaises(GitInventoryHold):
            plan_disposable_lifecycle(replace(intent,preflight=replace(intent.preflight,writes_allowed=True)),self.inventory())

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


from my_local_ai.gitops.worktree import audit_linked_worktree_metadata


class LinkedGitdirAttackTests(ScopePreflightTests):
    def install_link(self, *, target_override=None, back_override=None):
        root=self.original/".git"/"worktrees"
        root.mkdir(parents=True,exist_ok=True)
        selected=root/"w014"
        selected.mkdir()
        marker=self.worktree/".git"
        marker.write_text("gitdir: "+str(target_override or selected)+"\n",encoding="utf-8")
        (selected/"gitdir").write_text(str(back_override or marker)+"\n",encoding="utf-8")
        return marker,selected

    def intent(self):
        return plan_disposable(
            task_id="TASK-014",worktree=self.worktree,
            original_checkout=self.original,baseline_sha=SHA,
            allowed_paths=("src/new.py",),
        )

    def test_bidirectional_gitdir_is_read_only_evidence(self):
        marker,gitdir=self.install_link()
        v=audit_linked_worktree_metadata(self.intent())
        self.assertEqual(v.worktree_gitfile,str(marker))
        self.assertFalse(v.may_write_git)
        self.assertFalse(v.independent_f18_verified)
        self.assertTrue(gitdir.exists())

    def test_external_and_relative_gitdir_redirect_hold(self):
        root=self.root/"attacker"
        root.mkdir()
        self.install_link(target_override=root)
        with self.assertRaises(GitInventoryHold):
            audit_linked_worktree_metadata(self.intent())

    def test_gitdir_backlink_redirect_hold(self):
        self.install_link(back_override=self.original/".git")
        with self.assertRaises(GitInventoryHold):
            audit_linked_worktree_metadata(self.intent())

    def test_symlinked_gitfile_never_followed(self):
        marker,target=self.install_link()
        marker.unlink()
        try:
            marker.symlink_to(target/"gitdir")
        except OSError:
            self.skipTest("no symlink privileges")
        with self.assertRaises(GitInventoryHold):
            audit_linked_worktree_metadata(self.intent())

    def test_missing_gitdir_files_or_unknown_metadata_hold(self):
        self.install_link()
        (self.original/".git"/"worktrees"/"w014"/"gitdir").unlink()
        with self.assertRaises(GitInventoryHold):
            audit_linked_worktree_metadata(self.intent())


if __name__ == "__main__":
    unittest.main()



class ExtraWorktreeTraversalTests(ScopePreflightTests):
    def test_parent_dotdot_alias_rejected_even_when_target_exists(self):
        from my_local_ai.gitops.path_guard import ScopeHold
        for candidate in (self.worktree / ".." / "original",
                          self.root / "disposable" / ".." / "disposable"):
            with self.subTest(candidate=str(candidate)), self.assertRaises(ScopeHold):
                preflight_paths(
                    worktree=candidate, original_checkout=self.original,
                    baseline_sha=SHA, allowed_paths=("src/main.py",),
                )

    def test_original_dotdot_alias_refused(self):
        with self.assertRaises(ScopeHold):
            preflight_paths(
                worktree=self.worktree,
                original_checkout=self.original / ".." / "original",
                baseline_sha=SHA, allowed_paths=("src/main.py",),
            )

    def test_generator_overflow_terminates_after_seventeen_paths(self):
        seen=[]
        def excessive():
            for number in range(1000000):
                seen.append(number)
                yield f"src/path{number}.py"
        with self.assertRaises(ScopeHold):
            self.inspect(excessive())
        self.assertEqual(len(seen),17)

    def test_string_as_path_collection_not_accepted(self):
        with self.assertRaises(ScopeHold):
            self.inspect("src/main.py")

    def test_disposable_plan_task_ids_are_strict_alphanumeric(self):
        for tid in ("../owner", "TASK/014", "TASK 014", "TASK.014", "ø-task"):
            with self.subTest(tid=tid),self.assertRaises(ValueError):
                plan_disposable(
                    task_id=tid, worktree=self.worktree,
                    original_checkout=self.original,
                    baseline_sha=SHA,allowed_paths=("src/main.py",)
                )


class MetadataFileReplacementTests(LinkedGitdirAttackTests):
    def test_symlink_replacement_during_metadata_open_denied(self):
        from unittest.mock import patch
        import my_local_ai.gitops.worktree as worktree_module
        marker,target=self.install_link()
        real_open=worktree_module._os.open
        def swapping_open(path, flags, *args, **kwargs):
            if Path(path)==marker and marker.is_file() and not marker.is_symlink():
                marker.unlink()
                marker.symlink_to(target / "gitdir")
            return real_open(path,flags,*args,**kwargs)
        with patch.object(worktree_module._os,"open",side_effect=swapping_open):
            with self.assertRaises(GitInventoryHold):
                audit_linked_worktree_metadata(self.intent())
