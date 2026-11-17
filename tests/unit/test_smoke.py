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
