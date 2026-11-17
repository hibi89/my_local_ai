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


class SyntheticAggregationTests(unittest.TestCase):
    def test_bounded_aggregation_explicitly_not_real(self):
        t = module.SyntheticTrial
        m = module.SyntheticMetric
        sample = (t(m("qwen3:4b-synthetic", 1.5, 8, 80), "SIMULATED_SUCCESS"),
                  t(m("qwen3:4b-synthetic", 2.0, 0, 90), "SIMULATED_TIMEOUT", 1))
        summary = module.aggregate_synthetic_trials(sample)
        self.assertEqual((summary.attempt_count, summary.simulated_success_count,
                          summary.simulated_failure_count, summary.simulated_retry_count),
                         (2, 1, 1, 1))
        self.assertIn("NO_REAL_PERFORMANCE_CLAIM", summary.to_json())
        self.assertNotIn("tokens_per_second", summary.to_json())

    def test_invalid_sample_and_mixed_model_rejected(self):
        m = module.SyntheticMetric
        t = module.SyntheticTrial
        with self.assertRaises(ValueError):
            module.aggregate_synthetic_trials(())
        with self.assertRaises(ValueError):
            module.aggregate_synthetic_trials((t(m("3b", 1, 0, 1), "SIMULATED_SUCCESS"),
                                                t(m("4b", 1, 0, 1), "SIMULATED_TIMEOUT")))
        with self.assertRaises(ValueError):
            t(m("4b", 1, 5, 1), "SIMULATED_TIMEOUT")
        with self.assertRaises(ValueError):
            t(m("4b", 1, 0, 1), "SIMULATED_TIMEOUT", 2)

    def test_non_numeric_bool_and_label_injection_rejected(self):
        for value in (True, "1", float("inf")):
            with self.assertRaises(ValueError):
                module.SyntheticMetric("4b", value, 0, 1)
        for label in ("bad label", "x" * 81, "../private"):
            with self.assertRaises(ValueError):
                module.SyntheticMetric(label, 0, 0, 0)

    def test_failure_classification_never_exposes_message(self):
        self.assertEqual(module.classify_synthetic_failure(TimeoutError("SECRET")),
                         "SIMULATED_TIMEOUT")
        self.assertEqual(module.classify_synthetic_failure(MemoryError("private")),
                         "SIMULATED_RESOURCE_HOLD")
        self.assertEqual(module.classify_synthetic_failure(Exception("customer_path")),
                         "SIMULATED_UNKNOWN_FAILURE")
