"""Audit code is synthetic-only and cannot authorize source import."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_sources.py"
spec = importlib.util.spec_from_file_location("audit_sources", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
SOURCE = json.loads((ROOT / "docs" / "IMPORT_MANIFEST.json").read_text(encoding="utf-8"))

class SourceAuditTests(unittest.TestCase):
    def test_manifest_stays_blocked(self):
        out = module.audit_manifest(json.dumps(SOURCE))
        self.assertEqual(out["status"], "BLOCKED_PROVENANCE")
        self.assertEqual(out["source_imports"], 0)
        self.assertFalse(out["license_cleared"])
        self.assertEqual(out["candidate_files_pinned"], 5)

    def test_revision_drift_refused(self):
        changed = copy.deepcopy(SOURCE)
        changed["sources"][0]["commit_sha"] = "b" * 40
        with self.assertRaises(ValueError):
            module.audit_manifest(json.dumps(changed))

    def test_cannot_unblock_by_self_declaration(self):
        for field, value in (("imports", [{"path": "axdev/core.py"}]), ("import_decision", "APPROVED")):
            changed = copy.deepcopy(SOURCE)
            changed[field] = value
            with self.assertRaises(ValueError):
                module.audit_manifest(json.dumps(changed))

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            module.audit_manifest('{"version":1,"version":1}')

    def test_path_traversal_rejected(self):
        changed = copy.deepcopy(SOURCE)
        changed["sources"][0]["candidate_files"][0]["path"] = "../.env"
        with self.assertRaises(ValueError):
            module.audit_manifest(json.dumps(changed))

if __name__ == "__main__":
    unittest.main()
