"""Synthetic import smoke: no model, Git, network, or owner data."""
import unittest

class SmokeTests(unittest.TestCase):
    def test_contract_import(self):
        from my_local_ai.contracts import PlanSpec, TaskSpec, safe_path
        self.assertTrue(callable(PlanSpec.parse_json))
        self.assertTrue(callable(TaskSpec.parse))
        self.assertEqual(safe_path("src/demo.py"), "src/demo.py")

    def test_phase_is_not_verification(self):
        from my_local_ai.contracts import PlanSpec
        self.assertFalse(PlanSpec.__dataclass_fields__["approved"].default)


class MandatoryPhaseSafetySmokeTests(unittest.TestCase):
    def test_p1_source_does_not_unlock_p2_or_real_use(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        gates = json.loads((root / "WORK_PHASE_GATES.json").read_text(encoding="utf-8"))
        self.assertEqual(gates["current_phase"], "P1_IMPLEMENTATION")
        self.assertEqual(gates["p2"]["status"], "LOCKED")
        self.assertFalse(gates["p1"]["high_approved_candidate"])
        self.assertFalse(gates["p1"]["implementation_complete_candidate"])
        self.assertFalse(gates["p4"]["owner_go"])

    def test_existing_mandatory_github_ci_stays_read_only(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("dev/instant-implementation-v1", workflow)
        self.assertIn("compileall", workflow)
        self.assertIn("tests/security", workflow)
        self.assertNotIn("contents: write", workflow)
