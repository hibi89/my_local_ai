"""Synthetic-only benchmark fixture. Never invokes a model or network."""
from __future__ import annotations
import json
import math
from collections import Counter
import re
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class SyntheticMetric:
    model_label: str
    elapsed_seconds: float
    generated_tokens: int
    peak_ram_mb: float
    source: str = "SYNTHETIC_NOT_MEASURED"

    def __post_init__(self):
        if self.source != "SYNTHETIC_NOT_MEASURED":
            raise ValueError("synthetic results cannot be marked real")
        if not isinstance(self.model_label, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", self.model_label):
            raise ValueError("model label")
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
               for v in (self.elapsed_seconds, self.peak_ram_mb)):
            raise ValueError("metric must be finite and nonnegative")
        if type(self.generated_tokens) is not int or self.generated_tokens < 0:
            raise ValueError("token count")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, allow_nan=False)


# The following counters describe fabricated fixtures, never device throughput.
_SYNTHETIC_OUTCOMES = frozenset({
    "SIMULATED_SUCCESS", "SIMULATED_TIMEOUT", "SIMULATED_RESOURCE_HOLD",
    "SIMULATED_INVALID_OUTPUT", "SIMULATED_UNKNOWN_FAILURE",
})


@dataclass(frozen=True)
class SyntheticTrial:
    metric: SyntheticMetric
    outcome: str
    retries: int = 0

    def __post_init__(self):
        if not isinstance(self.metric, SyntheticMetric):
            raise ValueError("synthetic metric required")
        if self.outcome not in _SYNTHETIC_OUTCOMES:
            raise ValueError("invalid simulated outcome")
        if type(self.retries) is not int or not 0 <= self.retries <= 1:
            raise ValueError("only zero/one synthetic retries permitted")
        if self.outcome != "SIMULATED_SUCCESS" and self.metric.generated_tokens:
            raise ValueError("failed trial cannot report generated tokens")


@dataclass(frozen=True)
class SyntheticAggregate:
    model_label: str
    attempt_count: int
    simulated_success_count: int
    simulated_failure_count: int
    simulated_retry_count: int
    outcome_counts: tuple[tuple[str, int], ...]
    source: str = "SYNTHETIC_NOT_MEASURED"
    status: str = "NO_REAL_PERFORMANCE_CLAIM"

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, allow_nan=False)


def classify_synthetic_failure(error: BaseException) -> str:
    """Class-only classification: never serialize exception messages or paths."""
    if isinstance(error, TimeoutError):
        return "SIMULATED_TIMEOUT"
    if isinstance(error, MemoryError):
        return "SIMULATED_RESOURCE_HOLD"
    if isinstance(error, (ValueError, UnicodeError)):
        return "SIMULATED_INVALID_OUTPUT"
    return "SIMULATED_UNKNOWN_FAILURE"


def aggregate_synthetic_trials(trials: tuple[SyntheticTrial, ...]) -> SyntheticAggregate:
    if not isinstance(trials, tuple) or not 1 <= len(trials) <= 100:
        raise ValueError("bounded nonempty synthetic trials required")
    if any(not isinstance(x, SyntheticTrial) for x in trials):
        raise ValueError("all trials must be synthetic")
    model = trials[0].metric.model_label
    if any(t.metric.model_label != model for t in trials):
        raise ValueError("mixed model labels cannot be aggregated")
    counts = Counter(t.outcome for t in trials)
    successes = counts["SIMULATED_SUCCESS"]
    return SyntheticAggregate(
        model_label=model, attempt_count=len(trials),
        simulated_success_count=successes,
        simulated_failure_count=len(trials)-successes,
        simulated_retry_count=sum(t.retries for t in trials),
        outcome_counts=tuple(sorted(counts.items())),
    )


def synthetic_examples() -> tuple[SyntheticMetric, ...]:
    return (
        SyntheticMetric("synthetic-3b-placeholder", 0.0, 0, 0.0),
        SyntheticMetric("synthetic-4b-placeholder", 0.0, 0, 0.0),
    )

if __name__ == "__main__":
    for metric in synthetic_examples():
        print(metric.to_json())
