"""V1.3 source counter: traceable P1 status, never OS or F18 approval."""
import unittest
from my_local_ai.cli import _v13_swu_progress

class SourceProgressTests(unittest.TestCase):
    def test_integrated_source_count_and_denials(self):
        status = _v13_swu_progress()
        self.assertEqual(status["legacy_mla_source_swu_completed"], 35)
        self.assertEqual(status["codeshield_feature_source_candidates_at_merge"], 13)
        self.assertEqual(status["codeshield_source_candidates_integrated_into_dev"], 14)
        self.assertEqual(status["v13_implementation_source_swu_completed"], 49)
        self.assertEqual(status["v13_implementation_source_swu_total"], 55)
        self.assertEqual(status["v13_implementation_source_swu_percent"], 89.09)
        self.assertFalse(status["execution_allowed"])
        self.assertFalse(status["independent_f18_verified"])
        self.assertFalse(status["owner_go_verified"])
        self.assertEqual(status["p2"], "LOCKED")
        self.assertEqual(status["verification"], "UNASSESSED")

if __name__ == "__main__":
    unittest.main()
