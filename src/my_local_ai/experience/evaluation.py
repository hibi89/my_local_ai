"""MESA V2 bounded A/B accounting, never a performance or trust claim.

Measurement input is locally supplied *observation*. Without matched exact
source, plan, environment, scope and acceptance criteria the comparison is
UNMEASURED. Even matching untrusted observations are NOT independently
validated speedup evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


@dataclass(frozen=True, slots=True)
class TaskMetricsV1:
    observation_id: str
    variant: str
    project_id: str
    plan_sha256: str
    source_git_sha: str
    acceptance_sha256: str
    environment_digest: str
    scope_ref: str
    rights_tag: str
    elapsed_ms: int
    accepted_req_count: int
    model_calls: int
    attempts: int
    validation_ms: int
    cpu_peak_bytes: int | None
    ram_peak_bytes: int | None
    vram_peak_bytes: int | None

    def __post_init__(self):
        if (not isinstance(self.observation_id, str)
            or _ID.fullmatch(self.observation_id) is None
            or not isinstance(self.project_id, str)
            or _ID.fullmatch(self.project_id) is None
            or not isinstance(self.scope_ref, str)
            or _ID.fullmatch(self.scope_ref) is None
            or self.variant not in {"BASELINE", "ASSISTED"}
            or self.rights_tag not in {"PUBLIC_SYNTHETIC", "OWNED_REDACTED"}
            or any(not isinstance(getattr(self, n), str)
                   or _SHA64.fullmatch(getattr(self, n)) is None
                   for n in ("plan_sha256", "acceptance_sha256", "environment_digest"))
            or not isinstance(self.source_git_sha, str)
            or _SHA40.fullmatch(self.source_git_sha) is None
            or type(self.elapsed_ms) is not int or self.elapsed_ms <= 0
            or any(type(getattr(self, n)) is not int or getattr(self, n) < 0
                   for n in ("accepted_req_count", "model_calls", "attempts",
                             "validation_ms"))
            or self.validation_ms > self.elapsed_ms
            or any(v is not None and (type(v) is not int or v < 0)
                   for v in (self.cpu_peak_bytes, self.ram_peak_bytes,
                             self.vram_peak_bytes))):
            raise ValueError("invalid or unscoped task metrics")


@dataclass(frozen=True, slots=True)
class MetricsComparisonV1:
    state: str
    reasons: tuple[str, ...]
    baseline_reqs_per_hour: float | None = None
    assisted_reqs_per_hour: float | None = None
    baseline_elapsed_ms: int | None = None
    assisted_elapsed_ms: int | None = None
    baseline_calls: int | None = None
    assisted_calls: int | None = None
    baseline_validation_ms: int | None = None
    assisted_validation_ms: int | None = None
    assisted_vram_peak_bytes: int | None = None
    verified_speedup: str = "UNMEASURED"
    independent_evidence: bool = False

    def __post_init__(self):
        if (self.state not in {"UNMEASURED", "OBSERVED_UNVERIFIED"}
            or self.verified_speedup != "UNMEASURED"
            or self.independent_evidence is not False):
            raise ValueError("untrusted metrics cannot claim verified improvement")

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "state": self.state, "reasons": list(self.reasons),
            "baseline_reqs_per_hour": self.baseline_reqs_per_hour,
            "assisted_reqs_per_hour": self.assisted_reqs_per_hour,
            "baseline_elapsed_ms": self.baseline_elapsed_ms,
            "assisted_elapsed_ms": self.assisted_elapsed_ms,
            "baseline_calls": self.baseline_calls,
            "assisted_calls": self.assisted_calls,
            "baseline_validation_ms": self.baseline_validation_ms,
            "assisted_validation_ms": self.assisted_validation_ms,
            "assisted_vram_peak_bytes": self.assisted_vram_peak_bytes,
            "verified_speedup": "UNMEASURED",
            "independent_evidence": False,
            "owner_go": False, "execution_allowed": False,
        }


def compare_task_metrics(
    baseline: TaskMetricsV1 | None,
    assisted: TaskMetricsV1 | None,
) -> MetricsComparisonV1:
    if baseline is None or assisted is None:
        return MetricsComparisonV1("UNMEASURED", ("MISSING_OBSERVATION",))
    if not isinstance(baseline, TaskMetricsV1) or not isinstance(assisted, TaskMetricsV1):
        raise ValueError("unrecognized observation")
    if baseline.variant != "BASELINE" or assisted.variant != "ASSISTED":
        return MetricsComparisonV1("UNMEASURED", ("BAD_COMPARISON_VARIANTS",))
    exact = (
        "project_id", "plan_sha256", "source_git_sha", "acceptance_sha256",
        "environment_digest", "scope_ref", "rights_tag",
    )
    if any(getattr(baseline, k) != getattr(assisted, k) for k in exact):
        return MetricsComparisonV1("UNMEASURED", ("BASELINE_SCOPE_OR_SHA_DRIFT",))
    # Prevent same record being presented as two independent measurements.
    if baseline.observation_id == assisted.observation_id:
        return MetricsComparisonV1("UNMEASURED", ("DUPLICATED_OBSERVATION",))
    def rate(record: TaskMetricsV1) -> float:
        return round(record.accepted_req_count * 3600000 / record.elapsed_ms, 4)
    return MetricsComparisonV1(
        "OBSERVED_UNVERIFIED", ("LOCAL_OBSERVATIONS_NOT_INDEPENDENT",),
        rate(baseline), rate(assisted), baseline.elapsed_ms, assisted.elapsed_ms,
        baseline.model_calls, assisted.model_calls,
        baseline.validation_ms, assisted.validation_ms,
        assisted.vram_peak_bytes,
    )
