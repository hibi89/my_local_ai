"""Synthetic-only packaging gates; no protected service or Owner UI is executed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_protected_windows.py"
SPEC = importlib.util.spec_from_file_location("build_protected_windows", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class WindowsProtectedBuildTests(unittest.TestCase):
    def test_exact_four_entrypoints_and_no_selector(self):
        self.assertEqual({role for role, _, _ in module.IMAGES},
                         {"owner", "reviewer", "scanner", "owner-ui"})
        for role, _, _ in module.IMAGES:
            code = module.entrypoint_source(role)
            compile(code, "<frozen-entrypoint>", "exec")
            self.assertNotIn("sys.argv", code)
            if role == "owner-ui":
                self.assertIn("owner_session_main()", code)
            else:
                self.assertIn(f"protected_service_main('{role}')", code)
        with self.assertRaises(ValueError):
            module.entrypoint_source("controller")

    def test_bounded_one_folder_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "MyLocalAI.owner.v1"
            inner = root / "_internal"
            inner.mkdir(parents=True)
            (root / "MyLocalAI.owner.v1.exe").write_bytes(b"PE-placeholder-synthetic")
            (inner / "pkg.bin").write_bytes(b"synthetic")
            result = module.inspect_image(root, "MyLocalAI.owner.v1")
            self.assertEqual(result["internal_file_count"], 1)
            self.assertEqual(len(result["image_sha256"]), 64)
            (root / "extra.exe").write_bytes(b"not allowed")
            with self.assertRaises(ValueError):
                module.inspect_image(root, "MyLocalAI.owner.v1")
            (root / "extra.exe").unlink()
            (inner / "pkg.bin").unlink()
            with self.assertRaises(ValueError):
                module.inspect_image(root, "MyLocalAI.owner.v1")

    def test_unsupported_platform_never_installs_or_builds(self):
        import os
        if os.name == "nt":
            self.skipTest("platform denial asserted on non-Windows synthetic CI")
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "out"
            with self.assertRaises(RuntimeError):
                module.build_all(target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
