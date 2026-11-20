"""Unprivileged workbench liveness log, never a Windows/P2 acceptance gate."""
from __future__ import annotations

from contextlib import closing
import math
from pathlib import Path
import secrets
import sqlite3
from threading import Event, Lock, Thread
import time

from .draft_timing import _timing_path
from ..ops.resource_monitor import CpuTimeSnapshot, ResourceReading, sample_local_resources

_INTERVAL_SECONDS = 60
_MAX_ROWS = 4096
_GAP_SECONDS = 180


class LongrunMonitor:
    """Local-only, bounded SQLite samples; no restart or execution authority."""

    def __init__(self, root: Path, *, clock=time.monotonic, wall=time.time,
                 sampler=sample_local_resources):
        self.root = Path(root)
        self._clock = clock
        self._wall = wall
        self._sampler = sampler
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._session = secrets.token_hex(12)
        self._previous_cpu: CpuTimeSnapshot | None = None
        self._last_mono: float | None = None
        self._last_wall: float | None = None
        self._start_mono: float | None = None
        self._previous_unclean: bool | None = None
        self._gap_count = 0
        self._sample_count = 0
        self._health = "NOT_STARTED"
        self._reading = ResourceReading(None, None, None, None)

    def _record(self, event: str, now: float, elapsed: int, gap: bool,
                reading: ResourceReading) -> None:
        # Prompts, file paths, source, model output and secrets are never recorded.
        with closing(sqlite3.connect(_timing_path(self.root), timeout=3.0)) as db, db:
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("CREATE TABLE IF NOT EXISTS longrun_receipts ("
                       "id INTEGER PRIMARY KEY, session TEXT NOT NULL, event TEXT NOT NULL, "
                       "utc_seconds INTEGER NOT NULL, elapsed_seconds INTEGER NOT NULL, "
                       "gap INTEGER NOT NULL, system_ram_mb REAL, cpu_percent REAL)")
            if self._previous_unclean is None:
                last = db.execute("SELECT session, event FROM longrun_receipts "
                                  "ORDER BY id DESC LIMIT 1").fetchone()
                self._previous_unclean = bool(last and last[0] != self._session
                                              and last[1] != "STOP")
            def bounded(value: float | None, bound: float) -> float | None:
                return (round(float(value), 2) if type(value) in (int, float)
                        and math.isfinite(value) and 0 <= value <= bound else None)
            db.execute("INSERT INTO longrun_receipts "
                       "(session,event,utc_seconds,elapsed_seconds,gap,system_ram_mb,cpu_percent) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (self._session, event, max(0, int(now)), max(0, elapsed),
                        int(gap), bounded(reading.ram_mb, 262144),
                        bounded(reading.cpu_percent, 100)))
            db.execute("DELETE FROM longrun_receipts WHERE id NOT IN "
                       "(SELECT id FROM longrun_receipts ORDER BY id DESC LIMIT ?)",
                       (_MAX_ROWS,))

    def tick(self, event: str = "HEARTBEAT") -> None:
        if event not in {"START", "HEARTBEAT", "STOP"}:
            raise ValueError("unrecognized monitor event")
        with self._lock:
            mono, wall = self._clock(), self._wall()
            if not (math.isfinite(mono) and math.isfinite(wall)):
                self._health = "EVIDENCE_UNAVAILABLE"
                return
            if self._start_mono is None:
                self._start_mono = mono
            gap = False
            if self._last_mono is not None and self._last_wall is not None:
                dm, dw = mono - self._last_mono, wall - self._last_wall
                gap = (dm < 0 or dw < 0 or max(dm, dw) > _GAP_SECONDS
                       or abs(dm - dw) > 120)
            try:
                reading, previous = self._sampler(previous_cpu=self._previous_cpu)
                if not isinstance(reading, ResourceReading):
                    raise ValueError("unexpected sensor reading")
                self._record(event, wall, int(max(0, mono - self._start_mono)), gap, reading)
            except (OSError, ValueError, sqlite3.Error, OverflowError, TypeError):
                self._health = "EVIDENCE_UNAVAILABLE"
                return
            self._reading = reading
            self._previous_cpu = previous
            self._last_mono, self._last_wall = mono, wall
            self._sample_count += 1
            self._gap_count += int(gap)
            self._health = "LOCAL_UNATTESTED"

    def _run(self) -> None:
        while not self._stop.wait(_INTERVAL_SECONDS):
            self.tick()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("monitor already started")
        self.tick("START")
        self._thread = Thread(target=self._run, name="MLA-longrun-receipts", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if not self._thread.is_alive():
                self.tick("STOP")

    def snapshot(self) -> dict:
        with self._lock:
            reading = self._reading
            uptime = (max(0, int(self._clock() - self._start_mono))
                      if self._start_mono is not None else 0)
            def visible(value: float | None, maximum: float) -> float | None:
                return (round(float(value), 2) if type(value) in (int, float)
                        and math.isfinite(value) and 0 <= value <= maximum else None)
            return {"status": self._health, "verification": "NOT_RUN",
                    "real_24h_accepted": False, "session": self._session,
                    "uptime_seconds": uptime, "samples": self._sample_count,
                    "clock_or_sampling_gaps": self._gap_count,
                    "previous_session_unclosed": self._previous_unclean,
                    "system_ram_mb": visible(reading.ram_mb, 262144),
                    "cpu_percent": visible(reading.cpu_percent, 100),
                    "vram_mb": None, "temperature_c": None}
