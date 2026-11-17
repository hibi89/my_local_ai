"""Synthetic-only benchmark fixture. Never invokes a model or network."""
from __future__ import annotations
import json
import math
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
        if not self.model_label or len(self.model_label) > 80:
            raise ValueError("model label")
        if any(not math.isfinite(v) or v < 0 for v in (self.elapsed_seconds, self.peak_ram_mb)):
            raise ValueError("metric must be finite and nonnegative")
        if type(self.generated_tokens) is not int or self.generated_tokens < 0:
            raise ValueError("token count")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, allow_nan=False)

def synthetic_examples() -> tuple[SyntheticMetric, ...]:
    return (
        SyntheticMetric("synthetic-3b-placeholder", 0.0, 0, 0.0),
        SyntheticMetric("synthetic-4b-placeholder", 0.0, 0, 0.0),
    )

if __name__ == "__main__":
    for metric in synthetic_examples():
        print(metric.to_json())
