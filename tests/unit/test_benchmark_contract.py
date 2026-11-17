"""No Ollama or network dependency."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_synthetic.py"
spec = importlib.util.spec_from_file_location("benchmark_synthetic", SCRIPT)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class BenchmarkContractTests(unittest.TestCase):
    def test_synthetic_records_never_claim_real(self):
        records = module.synthetic_examples()
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record.source, "SYNTHETIC_NOT_MEASURED")
            self.assertIn("SYNTHETIC_NOT_MEASURED", record.to_json())

    def test_cannot_relabel_as_real(self):
        with self.assertRaises(ValueError):
            module.SyntheticMetric("4b", 1.0, 5, 20.0, "REAL_WINDOWS_PASS")

    def test_negative_and_nonfinite_rejected(self):
        for seconds in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                module.SyntheticMetric("4b", seconds, 1, 10.0)
