"""Synthetic contract tests: no external model, filesystem writes, or owner approval."""
import copy
import json
import unittest

from my_local_ai.contracts import PlanSpec, TaskSpec, safe_path, canonical_digest

SHA = "a" * 40

def sample():
    return {
        "version": 1, "plan_id": "SYNTH-001",
        "blueprint": {"repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1", "sha": SHA},
        "approval": {"status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None},
        "tasks": [{
            "task_id": "TASK-001", "req_ids": ["REQ-03"], "depends_on": [],
            "goal": "Synthetic only", "allowed_paths": ["src/demo.py"],
            "acceptance": ["demo works"], "checks": [["python", "-m", "unittest"]],
            "risk": "LOW", "resource_budget": {"max_calls": 2, "max_seconds": 120},
            "safety_checks": ["NO_REMOTE"], "plan_sha": None, "source_sha": SHA
        }]
    }

class ContractTests(unittest.TestCase):
    def test_parses_but_never_approves(self):
        plan = PlanSpec.parse_json(json.dumps(sample()))
        self.assertFalse(plan.approved)
        self.assertEqual(len(plan.digest), 64)
        self.assertEqual(plan.tasks[0].resource_budget.max_seconds, 120)

    def test_approval_claim_is_not_consent(self):
        obj = sample()
        digest = PlanSpec.parse_json(json.dumps(obj)).digest
        obj["tasks"][0]["plan_sha"] = digest
        obj["approval"] = {"status": "APPROVED", "scope": "LOCAL_DEVELOPMENT", "digest": canonical_digest({"plan_sha": digest, "scope": "LOCAL_DEVELOPMENT"})}
        claimed = PlanSpec.parse_json(json.dumps(obj))
        self.assertEqual(claimed.approval_status_claim, "APPROVED")
        self.assertFalse(claimed.approved)

    def test_mutated_plan_requires_rebind(self):
        obj = sample()
        obj["tasks"][0]["plan_sha"] = PlanSpec.parse_json(json.dumps(obj)).digest
        obj["tasks"][0]["goal"] = "Change original code"
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):
            PlanSpec.parse_json('{"version":1,"version":1}')

    def test_path_escape_rejected(self):
        for path in ("../secret", "/tmp/a", "C:/temp/a", "src/../secret", "src/*.py",
                     "src\\secret", "CON", "CON.txt", ".git/HEAD", ".env",
                     "a//b", "src/AUX.txt", "src/t\u00e9st.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_path(path)

    def test_casefold_path_duplicate_rejected(self):
        obj = sample()
        obj["tasks"][0]["allowed_paths"] = ["src/a.py", "src/A.py"]
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

    def test_unknown_dependency_rejected(self):
        obj = sample()
        obj["tasks"][0]["depends_on"] = ["TASK-999"]
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

    def test_cycle_rejected(self):
        obj = sample()
        obj["tasks"].append({**copy.deepcopy(obj["tasks"][0]), "task_id": "TASK-002", "depends_on": ["TASK-001"]})
        obj["tasks"][0]["depends_on"] = ["TASK-002"]
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

    def test_bad_budget_rejected(self):
        for budget in ({"max_calls": 0, "max_seconds": 10}, {"max_calls": True, "max_seconds": 10}, {"max_calls": 1, "max_seconds": -1}):
            obj = sample()
            obj["tasks"][0]["resource_budget"] = budget
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                PlanSpec.parse_json(json.dumps(obj))

    def test_missing_approval_rejected(self):
        obj = sample()
        del obj["approval"]
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

    def test_stale_baseline_sha_rejected(self):
        obj = sample()
        obj["tasks"][0]["source_sha"] = "b" * 40
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

if __name__ == "__main__":
    unittest.main()
