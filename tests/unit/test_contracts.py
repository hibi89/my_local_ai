import json
import unittest
from my_local_ai.contracts import PlanSpec, TaskSpec, safe_path

SHA = "a" * 40

def sample():
    return {"version": 1, "plan_id": "SYNTH-001", "blueprint": {"repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1", "sha": SHA}, "tasks": [{"task_id": "TASK-001", "req_ids": ["REQ-03"], "depends_on": [], "goal": "Synthetic only", "allowed_paths": ["src/demo.py"], "source_sha": SHA}]}

class ContractTests(unittest.TestCase):
    def test_parses_but_never_approves(self):
        p = PlanSpec.parse_json(json.dumps(sample()))
        self.assertFalse(p.approved)
        self.assertEqual(len(p.digest), 64)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):
            PlanSpec.parse_json('{"version":1,"version":1}')

    def test_path_escape_rejected(self):
        for path in ("../secret", "/tmp/a", "C:/temp/a", "src/../secret", "src/*.py", "src\\secret", "CON", "a//b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_path(path)

    def test_unknown_dependency_rejected(self):
        obj = sample()
        obj["tasks"][0]["depends_on"] = ["TASK-999"]
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

    def test_cycle_rejected(self):
        obj = sample()
        obj["tasks"].append({**obj["tasks"][0], "task_id": "TASK-002", "depends_on": ["TASK-001"]})
        obj["tasks"][0]["depends_on"] = ["TASK-002"]
        with self.assertRaises(ValueError):
            PlanSpec.parse_json(json.dumps(obj))

if __name__ == "__main__":
    unittest.main()
