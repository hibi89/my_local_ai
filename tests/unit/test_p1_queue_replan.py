"""P1 separate implementation vs execution dependencies; fully synthetic."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("p1_queue_replan", ROOT / "scripts/p1_queue_replan.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
SOURCE = json.loads((ROOT/"INSTANT_TASK_QUEUE.json").read_text(encoding="utf-8"))


class CodeQueueSeparationTests(unittest.TestCase):
    def audit(self, value):
        return mod.audit_p1_queue(json.dumps(value))

    def test_safe_code_only_ready_wave_has_no_runtime_go(self):
        report = self.audit(SOURCE)
        self.assertEqual(report["p1_code_ready"], tuple(SOURCE["first_ready"]))
        self.assertEqual(report["completed_req"], 5)
        self.assertEqual(SOURCE["p1_implementation_replan"]["completed_code_waves"][0], ["MLA-017","MLA-028","MLA-030"])
        self.assertEqual(report["runtime_actions_authorized"], 0)
        self.assertFalse(report["independent_f18_proven"])

    def test_try_fake_f18_or_owner_go_fails(self):
        for field,val in (("independent_f18","PASS"),("protected_owner_signer","READY"),("git_promotion","READY"),("p2","UNLOCKED"),("source_rights","APPROVED")):
            fake=copy.deepcopy(SOURCE)
            fake["p1_implementation_replan"][field]=val
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.audit(fake)

    def test_cannot_mark_executor_ready(self):
        fake=copy.deepcopy(SOURCE)
        fake["tasks"][16]["runtime_authorization"]="READY"
        with self.assertRaises(ValueError):
            self.audit(fake)
        fake=copy.deepcopy(SOURCE)
        fake["operational_ready"]=["MLA-017"]
        with self.assertRaises(ValueError):
            self.audit(fake)

    def test_code_ready_is_not_original_runtime_ready(self):
        for task in SOURCE["tasks"]:
            if task["p1_code_status"] == "READY_CODE_ONLY":
                self.assertEqual(task["status"], "BLOCKED_DEPENDENCY")
                self.assertTrue(task["runtime_dependencies_preserved"])

    def test_missing_source_evidence_denied(self):
        fake=copy.deepcopy(SOURCE)
        for item in fake["tasks"]:
            if item["task_id"] == SOURCE["tasks"][next(i for i,t in enumerate(SOURCE["tasks"]) if t["task_id"] == SOURCE["first_ready"][0])]["p1_code_depends_on"][0]:
                item["evidence_sha"]=None
        with self.assertRaises(ValueError):
            self.audit(fake)

    def test_code_ready_deps_stay_subset_original(self):
        fake=copy.deepcopy(SOURCE)
        target=next(t for t in fake["tasks"] if t["task_id"] == SOURCE["first_ready"][0])
        invalid=next(t["task_id"] for t in fake["tasks"] if t["task_id"] != target["task_id"] and t["task_id"] not in target["depends_on"])
        target["p1_code_depends_on"]=[invalid]
        with self.assertRaises(ValueError):
            self.audit(fake)

    def test_tamper_req_count_or_original_rights_denied(self):
        for field,value in (("total_code_req",29),("code_completed_req",30)):
            fake=copy.deepcopy(SOURCE);fake[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.audit(fake)
        fake=copy.deepcopy(SOURCE)
        fake["tasks"][0]["p1_code_status"]="READY_CODE_ONLY"
        with self.assertRaises(ValueError):
            self.audit(fake)


if __name__=="__main__":
    unittest.main()
