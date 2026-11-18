"""Metrics are comparable only for identical acceptance/source context."""
import unittest
from dataclasses import replace

from my_local_ai.experience.evaluation import (
    TaskMetricsV1, compare_task_metrics,
)

BASE = TaskMetricsV1(
    "baseline-001", "BASELINE", "project-001",
    "a"*64, "b"*40, "c"*64, "d"*64, "scope-001",
    "PUBLIC_SYNTHETIC", 120000, 2, 8, 3, 30000, 1000, 2000, None,
)
ASSISTED = replace(
    BASE, observation_id="assisted-001", variant="ASSISTED",
    elapsed_ms=60000, model_calls=4, attempts=2, validation_ms=10000,
)


class V2MetricsTest(unittest.TestCase):
    def test_matching_local_observation_is_not_verified_speedup(self):
        result = compare_task_metrics(BASE, ASSISTED)
        self.assertEqual(result.state, "OBSERVED_UNVERIFIED")
        self.assertEqual(result.baseline_reqs_per_hour, 60)
        self.assertEqual(result.assisted_reqs_per_hour, 120)
        self.assertEqual(result.verified_speedup, "UNMEASURED")
        self.assertFalse(result.independent_evidence)
        self.assertFalse(result.to_redacted_dict()["execution_allowed"])

    def test_exact_baseline_mismatch_is_unmeasured(self):
        for key, value in (
            ("source_git_sha", "e"*40),
            ("plan_sha256", "f"*64),
            ("acceptance_sha256", "0"*64),
            ("scope_ref", "scope-999"),
            ("environment_digest", "1"*64),
        ):
            with self.subTest(field=key):
                result = compare_task_metrics(BASE, replace(ASSISTED, **{key: value}))
                self.assertEqual(result.state, "UNMEASURED")
                self.assertIsNone(result.assisted_reqs_per_hour)
        self.assertEqual(compare_task_metrics(None, ASSISTED).state, "UNMEASURED")

    def test_invalid_forged_data_rejected(self):
        for key, value in (
            ("elapsed_ms", 0), ("model_calls", -1),
            ("attempts", True), ("ram_peak_bytes", -100),
            ("rights_tag", "CUSTOMER_PRIVATE"), ("source_git_sha", "bad"),
        ):
            with self.subTest(field=key), self.assertRaises(ValueError):
                replace(BASE, **{key: value})
        self.assertEqual(compare_task_metrics(
            BASE, replace(BASE, variant="ASSISTED")
        ).state, "UNMEASURED")


if __name__ == "__main__":
    unittest.main()
