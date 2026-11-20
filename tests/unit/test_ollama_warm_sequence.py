"""Synthetic Ollama warm-model boundaries; never starts Ollama or uses GPU."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from my_local_ai.ax_runtime.ollama_provider import OllamaProvider
from my_local_ai.ax_runtime.provider_policy import ProviderHold
from my_local_ai.ax_runtime.worker_lock import OneModelLock
from my_local_ai.ax_runtime.budgets import ModelBudget, BudgetGuard


class WarmModelTests(unittest.TestCase):
    def test_bounded_warm_keep_alive_changes_only_local_payload(self):
        provider = OllamaProvider(timeout_seconds=3)
        calls = []

        def request(method, path, *, payload=None, limit=None):
            calls.append((method, path, payload))
            if path == "/api/tags":
                return {"models": [{"name": "qwen3:4b-instruct"}]}
            if path == "/api/generate":
                return {"response": '{"summary":"x","files":[]}', "done": True}
            self.fail("unexpected external endpoint")

        with TemporaryDirectory() as folder, patch.object(provider, "_request", side_effect=request):
            for seconds in (90, 0):
                result = provider.generate(
                    "Produce one JSON draft", model_lock=OneModelLock(Path(folder)),
                    budget=BudgetGuard(ModelBudget(max_calls=1, max_context_tokens=4096,
                                                   max_output_bytes=1000, max_seconds=10)),
                    allow_generation=True, structured=True, keep_alive_seconds=seconds,
                )
                self.assertTrue(result.untrusted)
            request_payloads = [c[2] for c in calls if c[1] == "/api/generate"]
            self.assertEqual([p["keep_alive"] for p in request_payloads], ["90s", 0])
            self.assertEqual([p["model"] for p in request_payloads], ["qwen3:4b-instruct"]*2)
            self.assertTrue(all(p["options"]["num_ctx"] == 4096 for p in request_payloads))
            self.assertTrue(all(c[1] in ("/api/tags", "/api/generate") for c in calls))

    def test_keep_alive_denies_bad_or_unbounded_values_before_network(self):
        provider = OllamaProvider(timeout_seconds=3)
        with TemporaryDirectory() as folder, patch.object(provider, "_request") as request:
            for invalid in (-1, 91, True, "90", 0.5):
                with self.subTest(invalid=invalid), self.assertRaises(ProviderHold):
                    provider.generate(
                        "prompt", model_lock=OneModelLock(folder),
                        budget=BudgetGuard(ModelBudget()), allow_generation=True,
                        keep_alive_seconds=invalid,
                    )
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
