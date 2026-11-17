"""P1-only local benchmark harness. Default path is MOCK; real requires P2 owner GO."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
import re
import time
from typing import Callable, Protocol

from my_local_ai.ax_runtime.budgets import BudgetGuard, BudgetExceeded
from my_local_ai.ax_runtime.ollama_provider import OllamaProvider, UntrustedGeneration
from my_local_ai.ax_runtime.provider_policy import ProviderHold, require_qwen_model
from my_local_ai.ax_runtime.worker_lock import OneModelLock
from my_local_ai.contracts.approval import OwnerGrant, authorize_claim

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_FIXTURE = "SYNTHETIC_CODING_TASK_V1"


class BenchmarkHold(RuntimeError):
    def __init__(self, reason: str):
        reasons = {"P2_LOCKED", "NO_OWNER_GO", "OWNER_DEVICE_REQUIRED",
                   "BAD_BENCHMARK", "MODEL_UNAVAILABLE", "RESOURCE_LIMIT", "BAD_OBSERVATION", "MODEL_POLICY_HOLD", "INCONSISTENT_BATCH"}
        self.code = reason if reason in reasons else "BAD_OBSERVATION"
        super().__init__(self.code)


class LocalModel(Protocol):
    model: str

    def generate(self, prompt: str, *, model_lock: OneModelLock,
                 budget: BudgetGuard, allow_generation: bool) -> UntrustedGeneration: ...


@dataclass(frozen=True)
class BenchmarkPlan:
    model: str
    source_sha: str
    plan_sha256: str
    fixture_id: str = _FIXTURE
    repetitions: int = 1

    def __post_init__(self):
        try:
            require_qwen_model(self.model)
        except ProviderHold:
            raise BenchmarkHold("BAD_BENCHMARK") from None
        if (not isinstance(self.source_sha, str) or not _SHA40.fullmatch(self.source_sha)
            or not isinstance(self.plan_sha256, str) or not _SHA64.fullmatch(self.plan_sha256)
            or self.fixture_id != _FIXTURE or type(self.repetitions) is not int
            or not 1 <= self.repetitions <= 3):
            raise BenchmarkHold("BAD_BENCHMARK")


@dataclass(frozen=True)
class P2LocalPermit:
    """Must originate in trusted host, not guest or model."""
    implementation_sha: str
    high_approved: bool
    phase: str
    owner_device: bool


@dataclass(frozen=True)
class BenchmarkObservation:
    model: str
    source_sha: str
    plan_sha256: str
    fixture_id: str
    evidence_level: str
    elapsed_seconds: float
    output_bytes: int
    output_sha256: str
    tokens_generated: int | None
    peak_ram_mb: float | None
    peak_vram_mb: float | None
    power_watts: float | None
    accepted_req_per_hour: float | None
    status: str

    def __post_init__(self):
        if (self.evidence_level not in ("MOCK_ONLY", "LOCAL_MEASURED_P2_UNVERIFIED")
            or not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0
            or type(self.output_bytes) is not int or self.output_bytes < 0
            or not _SHA64.fullmatch(self.output_sha256) or self.status != "UNVERIFIED_CANDIDATE"
            or any(v is not None for v in (self.tokens_generated, self.peak_ram_mb,
                                          self.peak_vram_mb, self.power_watts,
                                          self.accepted_req_per_hour))):
            raise BenchmarkHold("BAD_OBSERVATION")

    def to_redacted_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, allow_nan=False)


def _observe(plan: BenchmarkPlan, *, model: LocalModel, prompt: str,
             model_lock: OneModelLock, budget: BudgetGuard,
             clock: Callable[[], float], level: str) -> tuple[BenchmarkObservation, ...]:
    if (not isinstance(prompt, str) or not prompt.strip() or "\x00" in prompt
        or not isinstance(model_lock, OneModelLock) or not isinstance(budget, BudgetGuard)
        or getattr(model, "model", None) != plan.model):
        raise BenchmarkHold("BAD_BENCHMARK")
    try:
        if len(prompt.encode("utf-8")) > 2048:
            raise BenchmarkHold("BAD_BENCHMARK")
    except UnicodeError:
        raise BenchmarkHold("BAD_BENCHMARK") from None
    if plan.repetitions > budget.limits.max_calls:
        raise BenchmarkHold("RESOURCE_LIMIT")
    records = []
    for _ in range(plan.repetitions):
        try:
            start = float(clock())
            result = model.generate(prompt, model_lock=model_lock,
                                    budget=budget, allow_generation=True)
            end = float(clock())
        except ProviderHold as error:
            raise BenchmarkHold(classify_benchmark_failure(error)) from None
        except BudgetExceeded:
            raise BenchmarkHold("RESOURCE_LIMIT") from None
        except (OSError, ValueError, TypeError, TimeoutError):
            raise BenchmarkHold("BAD_OBSERVATION") from None
        if (not math.isfinite(start) or not math.isfinite(end) or end < start
            or not isinstance(result, UntrustedGeneration) or result.untrusted is not True
            or result.model != plan.model):
            raise BenchmarkHold("BAD_OBSERVATION")
        try:
            if not isinstance(result.text, str):
                raise TypeError("invalid output type")
            raw = result.text.encode("utf-8")
        except (AttributeError, UnicodeError, TypeError):
            raise BenchmarkHold("BAD_OBSERVATION") from None
        if len(raw) > budget.limits.max_output_bytes:
            raise BenchmarkHold("RESOURCE_LIMIT")
        records.append(BenchmarkObservation(
            model=plan.model, source_sha=plan.source_sha, plan_sha256=plan.plan_sha256,
            fixture_id=plan.fixture_id, evidence_level=level, elapsed_seconds=end-start,
            output_bytes=len(raw), output_sha256=hashlib.sha256(raw).hexdigest(),
            tokens_generated=None, peak_ram_mb=None, peak_vram_mb=None,
            power_watts=None, accepted_req_per_hour=None, status="UNVERIFIED_CANDIDATE",
        ))
    return tuple(records)


def run_mock_benchmark(plan: BenchmarkPlan, *, fake_model: LocalModel, prompt: str,
                       model_lock: OneModelLock, budget: BudgetGuard,
                       clock: Callable[[], float]) -> tuple[BenchmarkObservation, ...]:
    """The mocked path rejects a real OllamaProvider to prevent P1 live calls."""
    if not isinstance(plan, BenchmarkPlan) or isinstance(fake_model, OllamaProvider):
        raise BenchmarkHold("P2_LOCKED")
    return _observe(plan, model=fake_model, prompt=prompt,
                    model_lock=model_lock, budget=budget, clock=clock, level="MOCK_ONLY")


def run_real_local_p2(
    plan: BenchmarkPlan, *, provider: OllamaProvider, prompt: str,
    model_lock: OneModelLock, budget: BudgetGuard,
    trusted_p2_permit: P2LocalPermit | None = None,
    owner_grant: OwnerGrant | None = None,
    trusted_hmac_key: bytes | None = None,
    live_consent_check: Callable[[str, str, str], bool] | None = None,
    now_seconds: int = 0, clock: Callable[[], float] = time.monotonic,
) -> tuple[BenchmarkObservation, ...]:
    """Future P2-only entry. No CLI/live call sites in P1.

    A separately protected controller must supply real gate/consent evidence.
    No benchmark record is F18-independent acceptance proof.
    """
    if (not isinstance(plan, BenchmarkPlan)
        or not isinstance(trusted_p2_permit, P2LocalPermit)
        or trusted_p2_permit.phase != "P2_VERIFICATION"
        or trusted_p2_permit.high_approved is not True
        or trusted_p2_permit.owner_device is not True
        or trusted_p2_permit.implementation_sha != plan.source_sha):
        raise BenchmarkHold("P2_LOCKED")
    if os.name != "nt":
        raise BenchmarkHold("OWNER_DEVICE_REQUIRED")
    if not authorize_claim(
        owner_grant, trusted_hmac_key=trusted_hmac_key,
        expected_plan_sha=plan.plan_sha256, expected_source_sha=plan.source_sha,
        required_scope="LOCAL_PLAN", now_seconds=now_seconds,
        trusted_live_consent_check=live_consent_check,
    ):
        raise BenchmarkHold("NO_OWNER_GO")
    if not isinstance(provider, OllamaProvider):
        raise BenchmarkHold("BAD_BENCHMARK")
    return _observe(plan, model=provider, prompt=prompt, model_lock=model_lock,
                    budget=budget, clock=clock, level="LOCAL_MEASURED_P2_UNVERIFIED")



@dataclass(frozen=True)
class BenchmarkBatchSummary:
    """A summary of candidate observations; never an acceptance or speed claim."""
    model: str
    source_sha: str
    plan_sha256: str
    fixture_id: str
    evidence_level: str
    attempts: int
    elapsed_total_seconds: float
    elapsed_min_seconds: float
    elapsed_max_seconds: float
    status: str = "UNVERIFIED_CANDIDATE"

    def to_redacted_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, allow_nan=False)


def classify_benchmark_failure(error: BaseException) -> str:
    """Finite redacted codes; do not export exception text or private paths."""
    if isinstance(error, BenchmarkHold):
        return error.code
    if isinstance(error, ProviderHold):
        if error.code in {"MODEL_ABSENT", "OLLAMA_UNAVAILABLE"}:
            return "MODEL_UNAVAILABLE"
        if error.code in {"RESOURCE_LIMIT", "NO_BUDGET", "NO_MODEL_LOCK"}:
            return "RESOURCE_LIMIT"
        return "MODEL_POLICY_HOLD"
    if isinstance(error, (BudgetExceeded, MemoryError)):
        return "RESOURCE_LIMIT"
    return "BAD_OBSERVATION"


def summarize_observations(
    observations: tuple[BenchmarkObservation, ...],
) -> BenchmarkBatchSummary:
    if not isinstance(observations, tuple) or not 1 <= len(observations) <= 3:
        raise BenchmarkHold("INCONSISTENT_BATCH")
    first = observations[0]
    if not isinstance(first, BenchmarkObservation):
        raise BenchmarkHold("INCONSISTENT_BATCH")
    signature = (first.model, first.source_sha, first.plan_sha256,
                 first.fixture_id, first.evidence_level)
    if any(not isinstance(item, BenchmarkObservation) or
           (item.model, item.source_sha, item.plan_sha256,
            item.fixture_id, item.evidence_level) != signature
           for item in observations):
        raise BenchmarkHold("INCONSISTENT_BATCH")
    durations = [item.elapsed_seconds for item in observations]
    total = math.fsum(durations)
    if not math.isfinite(total):
        raise BenchmarkHold("INCONSISTENT_BATCH")
    return BenchmarkBatchSummary(
        model=first.model, source_sha=first.source_sha,
        plan_sha256=first.plan_sha256, fixture_id=first.fixture_id,
        evidence_level=first.evidence_level, attempts=len(observations),
        elapsed_total_seconds=total,
        elapsed_min_seconds=min(durations),
        elapsed_max_seconds=max(durations),
    )
