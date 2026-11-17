"""Pure resource supervision limits, with no OS probes/process control in P1.

Unavailable memory, VRAM or thermal metrics never count as a successful
real-world benchmark. The trusted host may later supply these measurements;
this module cannot sample, start, stop or restart a model.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ResourceLimits:
    max_ram_mb: int = 12288
    max_vram_mb: int = 3072
    max_temperature_c: float = 85.0
    max_cpu_percent: float = 95.0

    def __post_init__(self):
        if (type(self.max_ram_mb) is not int or not 256 <= self.max_ram_mb <= 262144
            or type(self.max_vram_mb) is not int or not 128 <= self.max_vram_mb <= 262144
            or not isinstance(self.max_temperature_c,(float,int))
            or not math.isfinite(self.max_temperature_c)
            or not 30 <= self.max_temperature_c <= 105
            or not isinstance(self.max_cpu_percent,(float,int))
            or not math.isfinite(self.max_cpu_percent)
            or not 1 <= self.max_cpu_percent <= 100):
            raise ValueError("invalid resource limits")


@dataclass(frozen=True)
class ResourceReading:
    ram_mb: float | None
    vram_mb: float | None
    temperature_c: float | None
    cpu_percent: float | None
    source: str = "SYNTHETIC_UNKNOWN"


@dataclass(frozen=True)
class ResourceAssessment:
    state: str
    reasons: tuple[str, ...]
    may_start_worker: bool = False
    may_restart_worker: bool = False
    may_write_os: bool = False
    real_measurement_verified: bool = False


def assess_resources(reading: ResourceReading, limits: ResourceLimits) -> ResourceAssessment:
    if not isinstance(reading,ResourceReading) or not isinstance(limits,ResourceLimits):
        raise ValueError("unrecognized resource evidence")
    if reading.source not in {"SYNTHETIC_UNKNOWN", "TRUSTED_PLATFORM_P2_PENDING"}:
        raise ValueError("untrusted source type")
    data=((reading.ram_mb,limits.max_ram_mb,"RAM"),
          (reading.vram_mb,limits.max_vram_mb,"VRAM"),
          (reading.temperature_c,limits.max_temperature_c,"THERMAL"),
          (reading.cpu_percent,limits.max_cpu_percent,"CPU"))
    problems=[]
    for value,maximum,label in data:
        if value is None:
            problems.append("NOT_MEASURED_"+label)
        elif (type(value) not in (float,int) or not math.isfinite(value)
              or value < 0 or value > maximum):
            problems.append("UNSAFE_"+label)
    if problems:
        return ResourceAssessment("HOLD",tuple(problems))
    # A synthetic reading can be within limits but does NOT prove the real
    # platform, cooling, VRAM pressure, duration or execution authorization.
    return ResourceAssessment("WITHIN_DECLARED_LIMITS_UNVERIFIED",())


@dataclass(frozen=True)
class ResourceSample:
    sequence: int
    elapsed_seconds: int
    reading: ResourceReading


@dataclass(frozen=True)
class ResourceWindow:
    state: str
    duration_seconds: int
    reasons: tuple[str, ...]
    real_hardware_verified: bool = False
    may_restart_worker: bool = False


def assess_synthetic_window(
    samples: tuple[ResourceSample, ...], limits: ResourceLimits,
    *, min_samples: int = 3,
) -> ResourceWindow:
    """Detect missing/over-limit readings; never claim actual 24h operation."""
    if (not isinstance(samples, tuple) or not 1 <= len(samples) <= 128
        or type(min_samples) is not int or not 1 <= min_samples <= 128):
        raise ValueError("invalid resource window")
    previous=-1
    issues=[]
    for i,sample in enumerate(samples):
        if (not isinstance(sample,ResourceSample)
            or type(sample.sequence) is not int or sample.sequence != i
            or type(sample.elapsed_seconds) is not int
            or sample.elapsed_seconds <= previous):
            raise ValueError("untrusted sensor sequence or timestamp")
        previous=sample.elapsed_seconds
        check=assess_resources(sample.reading,limits)
        for reason in check.reasons:
            if reason not in issues:
                issues.append(reason)
    if len(samples)<min_samples:
        issues.append("INSUFFICIENT_SAMPLES")
    return ResourceWindow(
        "HOLD" if issues else "SYNTHETIC_WINDOW_NOT_REAL_DEVICE_PROVEN",
        samples[-1].elapsed_seconds-samples[0].elapsed_seconds,
        tuple(issues),
    )
