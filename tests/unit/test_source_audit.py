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

    def test_recursively_pinned_tree_evidence_cannot_be_forged(self):
        for name, change in (
            ("tree_sha", "f" * 40),
            ("entry_count", 0),
            ("tree_listing_truncated", True),
            ("filename_license_notice_hits", ["LICENSE"]),
            ("scan_scope", "RIGHTS_APPROVED"),
        ):
            altered = copy.deepcopy(SOURCE)
            altered["sources"][0]["full_tree_snapshot"][name] = change
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.audit_manifest(json.dumps(altered))

    def test_candidate_blob_and_inventory_changes_blocked(self):
        altered = copy.deepcopy(SOURCE)
        altered["sources"][1]["candidate_files"][0]["blob_sha"] = "f" * 40
        with self.assertRaises(ValueError):
            module.audit_manifest(json.dumps(altered))
        altered = copy.deepcopy(SOURCE)
        altered["sources"][0]["candidate_files"].pop()
        with self.assertRaises(ValueError):
            module.audit_manifest(json.dumps(altered))

    def test_path_traversal_rejected(self):
        changed = copy.deepcopy(SOURCE)
        changed["sources"][0]["candidate_files"][0]["path"] = "../.env"
        with self.assertRaises(ValueError):
            module.audit_manifest(json.dumps(changed))

if __name__ == "__main__":
    unittest.main()


class LivePinnedSourceAuditSafetyTests(unittest.TestCase):
    """Only fabricated GitHub API fixtures; no real HTTP or rights clearance."""

    def _fetch_fixture(self, *, branch_drift=False, notice=False):
        sources={entry["source_repo"]:entry for entry in SOURCE["sources"]}
        def read(repo, suffix):
            s=sources[repo]
            snapshot=s["full_tree_snapshot"]
            if suffix.startswith("git/commits/"):
                return {"sha":s["commit_sha"],"tree":{"sha":snapshot["tree_sha"]}}
            if suffix.startswith("git/trees/"):
                candidates=[
                    {"path":item["path"],"sha":item["blob_sha"],
                     "mode":"100644","type":"blob"}
                    for item in s["candidate_files"]
                ]
                count=snapshot["entry_count"]-len(candidates)
                others=[
                    {"path":f"extra/file-{i}.py","sha":"c"*40,
                     "mode":"100644","type":"blob"}
                    for i in range(count)
                ]
                if notice and repo == "hibi89/EAI":
                    others[0]["path"]="NOTICE.md"
                return {"sha":snapshot["tree_sha"],"truncated":False,
                        "tree":candidates+others}
            if suffix.startswith("branches/"):
                return {"commit":{"sha":("f"*40 if branch_drift and
                        repo=="hibi89/EAI" else s["commit_sha"])}}
            raise AssertionError("unapproved source fetch")
        return read

    def test_exact_commit_tree_is_still_provenance_hold(self):
        result=module.audit_live_pinned_github(
            json.dumps(SOURCE),fetch_json=self._fetch_fixture(),
        )
        self.assertEqual(result["source_tree_verified_count"],2)
        self.assertTrue(result["remote_live_sha_verified"])
        self.assertFalse(result["license_cleared"])
        self.assertEqual(result["source_imports"],0)
        self.assertEqual(result["status"],"BLOCKED_PROVENANCE")

    def test_branch_drift_not_mislabeled_as_current_pin(self):
        result=module.audit_live_pinned_github(
            json.dumps(SOURCE),fetch_json=self._fetch_fixture(branch_drift=True),
        )
        self.assertEqual(result["source_tree_verified_count"],2)
        self.assertFalse(result["remote_live_sha_verified"])
        self.assertEqual(result["status"],"BLOCKED_PROVENANCE")

    def test_notice_or_unavailable_source_never_clears_rights(self):
        with self.assertRaises(ValueError):
            module.audit_live_pinned_github(
                json.dumps(SOURCE),fetch_json=self._fetch_fixture(notice=True),
            )
        def unavailable(repo, suffix):
            raise ConnectionError("simulated public API outage")
        result=module.audit_live_pinned_github(
            json.dumps(SOURCE),fetch_json=unavailable,
        )
        self.assertEqual(result["source_tree_verified_count"],0)
        self.assertFalse(result["remote_live_sha_verified"])
        self.assertFalse(result["license_cleared"])
        self.assertTrue(all(
            item["status"]=="HOLD_REMOTE_EVIDENCE_UNAVAILABLE"
            for item in result["source_reads"]
        ))
