"""V1.3 source counter: traceable P1 status, never OS or F18 approval."""
import unittest
from my_local_ai.cli import _v13_swu_progress

class SourceProgressTests(unittest.TestCase):
    def test_integrated_source_count_and_denials(self):
        status = _v13_swu_progress()
        self.assertEqual(status["legacy_mla_source_swu_completed"], 37)
        self.assertEqual(status["codeshield_feature_source_candidates_at_merge"], 13)
        self.assertEqual(status["codeshield_source_candidates_integrated_into_dev"], 15)
        self.assertEqual(status["v13_implementation_source_swu_completed"], 52)
        self.assertEqual(status["v13_implementation_source_swu_total"], 55)
        self.assertEqual(status["v13_implementation_source_swu_percent"], 94.55)
        self.assertEqual(status["source_design_sha"], "05f51849c0efe7303bf57cb78dff576e441063f5")
        self.assertEqual(status["remaining_source_swu"], 3)
        self.assertFalse(status["zero_vm_container_dependency"])
        self.assertFalse(status["execution_allowed"])
        self.assertFalse(status["independent_f18_verified"])
        self.assertFalse(status["owner_go_verified"])
        self.assertEqual(status["p2"], "LOCKED")
        self.assertEqual(status["verification"], "UNASSESSED")

if __name__ == "__main__":
    unittest.main()
