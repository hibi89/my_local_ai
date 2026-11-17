"""Hard caps for local inference candidates; no process launches or model calls."""
from __future__ import annotations

from dataclasses import dataclass
import math
import threading
import time

class BudgetExceeded(RuntimeError):
    pass

@dataclass(frozen=True)
class ModelBudget:
    max_calls: int = 2
    max_seconds: int = 120
    max_ram_mb: int = 8192
    max_context_tokens: int = 8192
    max_output_bytes: int = 262144
    max_changed_files: int = 16
    max_disk_mb: int = 1024

    def __post_init__(self):
        caps = {
            "max_calls": (1,100),
            "max_seconds": (1,86400),
            "max_ram_mb": (256,16384),
            "max_context_tokens": (256,131072),
            "max_output_bytes": (1,10485760),
            "max_changed_files": (1,64),
            "max_disk_mb": (1,10240),
        }
        for key, (lower, upper) in caps.items():
            value = getattr(self, key)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError("invalid resource cap: " + key)

class BudgetGuard:
    def __init__(self, limits: ModelBudget, *, clock=None):
        if not isinstance(limits, ModelBudget):
            raise TypeError("validated ModelBudget required")
        self.limits = limits
        self._clock = clock or time.monotonic
        self._started = self._clock()
        self._lock = threading.Lock()
        self._calls = 0

    def check(self, *, ram_mb: float = 0, context_tokens: int = 0,
              output_bytes: int = 0, changed_files: int = 0, disk_mb: float = 0) -> None:
        with self._lock:
            if self._clock() - self._started > self.limits.max_seconds:
                raise BudgetExceeded("elapsed time limit")
            for field, amount, maximum in (
                ("ram", ram_mb, self.limits.max_ram_mb),
                ("context", context_tokens, self.limits.max_context_tokens),
                ("output", output_bytes, self.limits.max_output_bytes),
                ("files", changed_files, self.limits.max_changed_files),
                ("disk", disk_mb, self.limits.max_disk_mb),
            ):
                if (isinstance(amount, bool) or not isinstance(amount, (int, float))
                    or not math.isfinite(amount) or amount < 0 or amount > maximum):
                    raise BudgetExceeded("invalid/excessive " + field + " budget")

    def reserve_call(self) -> int:
        with self._lock:
            if self._clock() - self._started > self.limits.max_seconds:
                raise BudgetExceeded("elapsed time limit")
            if self._calls >= self.limits.max_calls:
                raise BudgetExceeded("model call limit")
            self._calls += 1
            return self._calls
