"""Local workbench process-exclusivity regression. No native Owner privilege."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from my_local_ai.ax_runtime.draft_documents import DraftError
from my_local_ai.ax_runtime.workbench_guard import exclusive_workbench


class WorkbenchGuardTests(unittest.TestCase):
    def test_same_root_cannot_have_two_live_workbenches_and_can_reopen(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "drafts"
            root.mkdir()
            with exclusive_workbench(root):
                with self.assertRaisesRegex(DraftError, "이미 실행 중"):
                    with exclusive_workbench(root):
                        self.fail("same root must be held exclusively")
            with exclusive_workbench(root):
                self.assertEqual((root / ".mla-workbench.instance.lock").read_bytes(), b"0")

    def test_independent_roots_can_run_and_corrupt_lock_fails_closed(self):
        with TemporaryDirectory() as directory:
            one = Path(directory) / "one"
            two = Path(directory) / "two"
            one.mkdir()
            two.mkdir()
            with exclusive_workbench(one), exclusive_workbench(two):
                pass
            (one / ".mla-workbench.instance.lock").write_bytes(b"bad")
            with self.assertRaises(DraftError):
                with exclusive_workbench(one):
                    self.fail("corrupt lock must HOLD")

    def test_symlink_lock_is_denied(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "drafts"
            root.mkdir()
            target = Path(directory) / "real"
            target.write_bytes(b"0")
            link = root / ".mla-workbench.instance.lock"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unsupported")
            with self.assertRaises(DraftError):
                with exclusive_workbench(root):
                    self.fail("symlink must be denied")


if __name__ == "__main__":
    unittest.main()
