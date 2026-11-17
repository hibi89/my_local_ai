"""P1 isolated fake-only benchmark checks; no actual model, device or network."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

from my_local_ai.ax_runtime.budgets import BudgetGuard, ModelBudget
from my_local_ai.ax_runtime.ollama_provider import OllamaProvider, UntrustedGeneration
from my_local_ai.ax_runtime.worker_lock import OneModelLock

PATH = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_real_local.py"
SPEC = importlib.util.spec_from_file_location("mla_benchmark_real_local", PATH)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)

SOURCE = "a" * 40
PLAN = "b" * 64


class FakeModel:
    model = "qwen3:4b-instruct"

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, *, model_lock, budget, allow_generation):
        self.calls += 1
        self.enabled = allow_generation
        return UntrustedGeneration("mock-result-not-a-pass", self.model)


class BenchmarkHarnessSecurityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lock = OneModelLock(tmp.name)
        self.budget = BudgetGuard(ModelBudget())
        self.plan = mod.BenchmarkPlan("qwen3:4b-instruct", SOURCE, PLAN)

    def mock(self, fake, prompt="synthetic", clock=None, plan=None):
        return mod.run_mock_benchmark(
            plan or self.plan, fake_model=fake, prompt=prompt,
            model_lock=self.lock, budget=self.budget,
            clock=clock or iter([2.0, 3.5]).__next__,
        )

    def test_p2_locked_default_denies_any_live_model(self):
        fake = FakeModel()
        with self.assertRaises(mod.BenchmarkHold) as err:
            mod.run_real_local_p2(self.plan, provider=fake, prompt="fixture",
                                  model_lock=self.lock, budget=self.budget)
        self.assertEqual(err.exception.code, "P2_LOCKED")
        self.assertEqual(fake.calls, 0)

    def test_false_approval_never_invokes_model(self):
        fake = FakeModel()
        bad_permit = mod.P2LocalPermit(SOURCE, False, "P2_VERIFICATION", True)
        with self.assertRaises(mod.BenchmarkHold) as err:
            mod.run_real_local_p2(self.plan, provider=fake, prompt="fixture",
                                  model_lock=self.lock, budget=self.budget,
                                  trusted_p2_permit=bad_permit)
        self.assertEqual(err.exception.code, "P2_LOCKED")
        self.assertEqual(fake.calls, 0)

    def test_real_ollama_rejected_on_mock_path(self):
        with self.assertRaises(mod.BenchmarkHold) as err:
            self.mock(OllamaProvider())
        self.assertEqual(err.exception.code, "P2_LOCKED")

    def test_mock_measures_only_duration_and_redacted_hash(self):
        fake = FakeModel()
        result = self.mock(fake, prompt="SENSITIVE_PROMPT_CANARY")[0]
        self.assertEqual(fake.calls, 1)
        self.assertTrue(fake.enabled)
        self.assertEqual(result.evidence_level, "MOCK_ONLY")
        self.assertEqual(result.status, "UNVERIFIED_CANDIDATE")
        self.assertEqual(result.elapsed_seconds, 1.5)
        self.assertIsNone(result.peak_ram_mb)
        self.assertIsNone(result.accepted_req_per_hour)
        self.assertEqual(result.output_sha256, hashlib.sha256(b"mock-result-not-a-pass").hexdigest())
        self.assertNotIn("SENSITIVE_PROMPT_CANARY", result.to_redacted_json())
        self.assertNotIn("mock-result-not-a-pass", result.to_redacted_json())

    def test_invalid_model_sha_fixture_and_repetitions(self):
        for args in (
            ("gpt:cloud", SOURCE, PLAN, "SYNTHETIC_CODING_TASK_V1", 1),
            ("qwen3:4b-instruct", SOURCE[:-1], PLAN, "SYNTHETIC_CODING_TASK_V1", 1),
            ("qwen3:4b-instruct", SOURCE, PLAN, "PRIVATE_SECRET", 1),
            ("qwen3:4b-instruct", SOURCE, PLAN, "SYNTHETIC_CODING_TASK_V1", 50),
        ):
            with self.subTest(args=args), self.assertRaises(mod.BenchmarkHold):
                mod.BenchmarkPlan(*args)

    def test_wrong_model_or_resource_limit_denied(self):
        fake = FakeModel()
        fake.model = "qwen3:8b"
        with self.assertRaises(mod.BenchmarkHold):
            self.mock(fake)
        self.assertEqual(fake.calls, 0)
        too_many = mod.BenchmarkPlan("qwen3:4b-instruct", SOURCE, PLAN, repetitions=3)
        with self.assertRaises(mod.BenchmarkHold):
            self.mock(FakeModel(), plan=too_many)

    def test_nonfinite_clock_denied(self):
        with self.assertRaises(mod.BenchmarkHold) as err:
            self.mock(FakeModel(), clock=iter([float("nan"), 1.]).__next__)
        self.assertEqual(err.exception.code, "BAD_OBSERVATION")

    def test_prompt_invalid_and_zero_calls(self):
        fake = FakeModel()
        with self.assertRaises(mod.BenchmarkHold):
            self.mock(fake, prompt="")
        self.assertEqual(fake.calls, 0)


if __name__ == "__main__":
    unittest.main()


class BenchmarkAggregationTests(unittest.TestCase):
    setUp = BenchmarkHarnessSecurityTests.setUp
    mock = BenchmarkHarnessSecurityTests.mock

    def test_summary_keeps_mock_scope_and_never_invents_speed(self):
        fake = FakeModel()
        result = self.mock(fake)
        summary = mod.summarize_observations(result)
        self.assertEqual(summary.attempts, 1)
        self.assertEqual(summary.elapsed_total_seconds, 1.5)
        self.assertEqual(summary.evidence_level, "MOCK_ONLY")
        self.assertNotIn("tokens_per_second", summary.to_redacted_json())
        self.assertNotIn("VERIFIED_PASS", summary.to_redacted_json())

    def test_summary_rejects_mixed_source_sha_and_empty(self):
        first = self.mock(FakeModel())[0]
        from dataclasses import replace
        second = replace(first, source_sha="c" * 40)
        with self.assertRaises(mod.BenchmarkHold) as err:
            mod.summarize_observations((first, second))
        self.assertEqual(err.exception.code, "INCONSISTENT_BATCH")
        with self.assertRaises(mod.BenchmarkHold):
            mod.summarize_observations(())

    def test_failure_classification_redacted_and_separate_policy(self):
        from my_local_ai.ax_runtime.provider_policy import ProviderHold
        self.assertEqual(mod.classify_benchmark_failure(ProviderHold("MODEL_ABSENT")),
                         "MODEL_UNAVAILABLE")
        self.assertEqual(mod.classify_benchmark_failure(ProviderHold("UNSAFE_ENDPOINT")),
                         "MODEL_POLICY_HOLD")
        self.assertEqual(mod.classify_benchmark_failure(TimeoutError("SECRET")),
                         "BAD_OBSERVATION")

    def test_mock_rejects_malformed_generated_text(self):
        class BadModel(FakeModel):
            def generate(self, prompt, *, model_lock, budget, allow_generation):
                return UntrustedGeneration(None, self.model)
        with self.assertRaises(mod.BenchmarkHold) as err:
            self.mock(BadModel())
        self.assertEqual(err.exception.code, "BAD_OBSERVATION")



class BenchmarkObservationHardeningTests(unittest.TestCase):
    def test_fake_clock_boolean_is_not_elapsed_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(mod.BenchmarkHold) as ctx:
                mod.run_mock_benchmark(
                    mod.BenchmarkPlan("qwen3:4b-instruct",SOURCE,PLAN),
                    fake_model=FakeModel(), prompt="synthetic",
                    model_lock=OneModelLock(tmp),
                    budget=BudgetGuard(ModelBudget()),
                    clock=iter([True,2]).__next__,
                )
        self.assertEqual(ctx.exception.code,"BAD_OBSERVATION")

    def test_forged_observation_sha_and_duration_fail_safely(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as tmp:
            baseline=mod.run_mock_benchmark(
                mod.BenchmarkPlan("qwen3:4b-instruct",SOURCE,PLAN),
                fake_model=FakeModel(),prompt="synthetic",
                model_lock=OneModelLock(tmp),
                budget=BudgetGuard(ModelBudget()),
                clock=iter([1.,2.]).__next__,
            )[0]
        for field in ({"elapsed_seconds":True},
                      {"output_sha256":None},
                      {"source_sha":"bad"},
                      {"plan_sha256":"bad"}):
            with self.subTest(field=field),self.assertRaises(mod.BenchmarkHold):
                replace(baseline,**field)

    def test_mock_output_consumes_budget_checks_before_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=iter([0.,2.]).__next__
            limit=BudgetGuard(ModelBudget(max_seconds=1),clock=lambda:0.)
            class SlowBudget(BudgetGuard):
                def __init__(self):
                    self.t=0
                    super().__init__(ModelBudget(max_seconds=1),clock=lambda:self.t)
                def check(self, **kwargs):
                    self.t+=0.6
                    return super().check(**kwargs)
            with self.assertRaises(mod.BenchmarkHold) as ctx:
                mod.run_mock_benchmark(
                    mod.BenchmarkPlan("qwen3:4b-instruct",SOURCE,PLAN),
                    fake_model=FakeModel(),prompt="synthetic",
                    model_lock=OneModelLock(tmp),budget=SlowBudget(),
                    clock=clock,
                )
            self.assertEqual(ctx.exception.code,"RESOURCE_LIMIT")
