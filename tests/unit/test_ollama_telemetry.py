"""Local model performance metrics are optional, bounded and contain no source text."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from my_local_ai.ax_runtime.budgets import BudgetGuard, ModelBudget
from my_local_ai.ax_runtime.ollama_provider import OllamaProvider, _safe_local_metrics
from my_local_ai.ax_runtime.worker_lock import OneModelLock


class TelemetryTests(unittest.TestCase):
    def test_ollama_exact_statistics_are_sanitized_without_prompt_echo(self):
        provider = OllamaProvider()
        calls = []
        def api(method, path, *, payload=None, limit=None):
            calls.append(path)
            if path == "/api/tags":
                return {"models": [{"name": "qwen3:4b-instruct"}]}
            return {"done": True, "response": "UNTRUSTED_SECRET_SOURCE",
                    "total_duration": 8_000_000_000, "load_duration": 3_000_000_000,
                    "prompt_eval_duration": 1_000_000_000, "eval_duration": 2_000_000_000,
                    "prompt_eval_count": 300, "eval_count": 100}
        with TemporaryDirectory() as folder, patch.object(provider, "_request", side_effect=api):
            output = provider.generate(
                "private prompt", model_lock=OneModelLock(Path(folder)),
                budget=BudgetGuard(ModelBudget(max_calls=1)),
                allow_generation=True, structured=True)
        self.assertEqual(calls, ["/api/tags", "/api/generate"])
        self.assertTrue(output.untrusted)
        self.assertEqual(output.metrics, {"total_ms": 8000, "load_ms": 3000,
                                         "prompt_ms": 1000, "eval_ms": 2000,
                                         "prompt_tokens": 300, "eval_tokens": 100,
                                         "tokens_per_second": 50.0})
        self.assertNotIn("private prompt", str(output.metrics))
        self.assertNotIn("UNTRUSTED_SECRET_SOURCE", str(output.metrics))

    def test_absent_or_malicious_metrics_are_ignored_not_fabricated(self):
        valid = {"total_duration": 2_000_000_000, "load_duration": 1,
                 "prompt_eval_duration": 10, "eval_duration": 0,
                 "prompt_eval_count": 9, "eval_count": 0}
        self.assertEqual(_safe_local_metrics(valid)["tokens_per_second"], 0.0)
        for mutation in ({"eval_count": True}, {"total_duration": -1},
                         {"load_duration": 900_000_000_001},
                         {"prompt_eval_count": "secret"},
                         {"eval_duration": None}):
            with self.subTest(mutation=mutation):
                self.assertIsNone(_safe_local_metrics({**valid, **mutation}))
        self.assertIsNone(_safe_local_metrics({"done": True, "response": "okay"}))


if __name__ == "__main__":
    unittest.main()
