"""Unprivileged workbench liveness log, never a Windows/P2 acceptance gate."""
from __future__ import annotations

from contextlib import closing
import math
import os
from pathlib import Path
import secrets
import sqlite3
from threading import Event, Lock, Thread
import time

from .draft_timing import _timing_path
from ..ops.resource_monitor import CpuTimeSnapshot, ResourceReading, sample_local_resources
from ..ops.nvml_readonly import NvidiaVramReading, sample_nvidia_vram

_INTERVAL_SECONDS = 60
_MAX_ROWS = 4096
_GAP_SECONDS = 180


def sample_process_ram_mb() -> float | None:
    """Read this MLA process working-set RSS on Windows; no elevation or subprocess."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(),
                                         ctypes.byref(counters), counters.cb):
            return None
        mb = counters.WorkingSetSize / (1024 * 1024)
        return round(mb, 2) if math.isfinite(mb) and 0 <= mb <= 262144 else None
    except (OSError, AttributeError, TypeError, ValueError, OverflowError):
        return None



def _read_previous_session(db: sqlite3.Connection) -> dict | None:
    """Read bounded local receipts; never grant P2 or restart authority."""
    last = db.execute("SELECT session FROM longrun_receipts ORDER BY id DESC LIMIT 1").fetchone()
    if last is None:
        return None
    session = last[0]
    if (type(session) is not str or len(session) != 24
        or any(ch not in "0123456789abcdef" for ch in session)):
        raise ValueError("invalid longrun session identity")
    rows = db.execute(
        "SELECT event, elapsed_seconds, gap FROM longrun_receipts "
        "WHERE session = ? ORDER BY id DESC LIMIT ?",
        (session, _MAX_ROWS),
    ).fetchall()
    rows.reverse()
    if not rows:
        raise ValueError("missing longrun receipts")
    gaps = 0
    prior_elapsed = None
    for index, (event, elapsed, gap) in enumerate(rows):
        if (event not in ("START", "HEARTBEAT", "STOP")
            or type(elapsed) is not int or elapsed < 0
            or type(gap) is not int or gap not in (0, 1)
            or (prior_elapsed is not None and elapsed < prior_elapsed)
            or (event == "START" and index != 0)
            or (event == "STOP" and index != len(rows) - 1)):
            raise ValueError("invalid longrun receipt order")
        inferred_gap = prior_elapsed is not None and elapsed - prior_elapsed > _GAP_SECONDS
        gaps += int(bool(gap or inferred_gap))
        prior_elapsed = elapsed
    start_present = rows[0][0] == "START"
    ended_cleanly = rows[-1][0] == "STOP"
    return {
        "samples": len(rows),
        "observed_span_seconds": rows[-1][1] - rows[0][1],
        "clock_or_sampling_gaps": gaps,
        "start_receipt_present": start_present,
        "ended_cleanly": ended_cleanly,
        "history_complete": start_present and ended_cleanly and gaps == 0,
        "verification": "NOT_RUN",
        "real_24h_accepted": False,
    }


class LongrunMonitor:
    """Local-only, bounded SQLite samples; no restart or execution authority."""

    def __init__(self, root: Path, *, clock=time.monotonic, wall=time.time,
                 sampler=sample_local_resources, process_sampler=sample_process_ram_mb,
                 gpu_sampler=sample_nvidia_vram):
        self.root = Path(root)
        self._clock = clock
        self._wall = wall
        self._sampler = sampler
        self._process_sampler = process_sampler
        self._gpu_sampler = gpu_sampler
        self._stop = Event()
        self._lock = Lock()
        self._stop_lock = Lock()
        self._stopped = False
        self._thread: Thread | None = None
        self._session = secrets.token_hex(12)
        self._previous_cpu: CpuTimeSnapshot | None = None
        self._last_mono: float | None = None
        self._last_wall: float | None = None
        self._start_mono: float | None = None
        self._previous_unclean: bool | None = None
        self._previous_session: dict | None = None
        self._gap_count = 0
        self._sample_count = 0
        self._health = "NOT_STARTED"
        self._reading = ResourceReading(None, None, None, None)
        self._process_ram_mb: float | None = None
        self._peak_process_ram_mb: float | None = None
        self._gpu_vram: NvidiaVramReading | None = None

    def _record(self, event: str, now: float, elapsed: int, gap: bool,
                reading: ResourceReading, process_ram_mb: float | None,
                gpu_vram: NvidiaVramReading | None) -> None:
        # Prompts, file paths, source, model output and secrets are never recorded.
        with closing(sqlite3.connect(_timing_path(self.root), timeout=3.0)) as db, db:
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("CREATE TABLE IF NOT EXISTS longrun_receipts ("
                       "id INTEGER PRIMARY KEY, session TEXT NOT NULL, event TEXT NOT NULL, "
                       "utc_seconds INTEGER NOT NULL, elapsed_seconds INTEGER NOT NULL, "
                       "gap INTEGER NOT NULL, system_ram_mb REAL, cpu_percent REAL)")
            if self._previous_unclean is None:
                previous = _read_previous_session(db)
                # No older receipts means no evidence of a previous crash.
                # An absent/partial STOP must never be labeled clean.
                self._previous_session = previous
                self._previous_unclean = bool(previous and not previous["ended_cleanly"])
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
            # Additive separate table: preserve the older local receipt schema.
            db.execute("CREATE TABLE IF NOT EXISTS longrun_process_ram "
                       "(receipt_id INTEGER PRIMARY KEY, working_set_mb REAL NOT NULL)")
            if process_ram_mb is not None:
                db.execute("INSERT INTO longrun_process_ram VALUES (?, ?)",
                           (db.execute("SELECT max(id) FROM longrun_receipts").fetchone()[0], process_ram_mb))
            db.execute("DELETE FROM longrun_process_ram WHERE receipt_id NOT IN "
                       "(SELECT id FROM longrun_receipts)")
            db.execute("CREATE TABLE IF NOT EXISTS longrun_gpu_vram "
                       "(receipt_id INTEGER PRIMARY KEY, used_mb REAL NOT NULL, "
                       "total_mb REAL NOT NULL)")
            if gpu_vram is not None:
                db.execute("INSERT INTO longrun_gpu_vram VALUES (?, ?, ?)",
                           (db.execute("SELECT max(id) FROM longrun_receipts").fetchone()[0],
                            gpu_vram.used_mb, gpu_vram.total_mb))
            db.execute("DELETE FROM longrun_gpu_vram WHERE receipt_id NOT IN "
                       "(SELECT id FROM longrun_receipts)")

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
                try:
                    process_ram = self._process_sampler()
                except (OSError, AttributeError, TypeError, ValueError, OverflowError):
                    process_ram = None
                if (type(process_ram) not in (float, int) or
                    not math.isfinite(process_ram) or not 0 <= process_ram <= 262144):
                    process_ram = None
                try:
                    gpu = self._gpu_sampler()
                except (OSError, AttributeError, TypeError, ValueError, OverflowError):
                    gpu = None
                if (not isinstance(gpu, NvidiaVramReading)
                    or type(gpu.used_mb) not in (float, int)
                    or type(gpu.total_mb) not in (float, int)
                    or not math.isfinite(gpu.used_mb)
                    or not math.isfinite(gpu.total_mb)
                    or not 0 <= gpu.used_mb <= gpu.total_mb <= 131072
                    or gpu.total_mb == 0):
                    gpu = None
                self._record(event, wall, int(max(0, mono - self._start_mono)), gap,
                             reading, process_ram, gpu)
            except (OSError, ValueError, sqlite3.Error, OverflowError, TypeError):
                self._health = "EVIDENCE_UNAVAILABLE"
                return
            self._reading = reading
            self._process_ram_mb = process_ram
            self._gpu_vram = gpu
            if process_ram is not None:
                self._peak_process_ram_mb = max(self._peak_process_ram_mb or 0, process_ram)
            self._previous_cpu = previous
            self._last_mono, self._last_wall = mono, wall
            self._sample_count += 1
            self._gap_count += int(gap)
            self._health = "LOCAL_UNATTESTED"

    def _run(self) -> None:
        while not self._stop.wait(_INTERVAL_SECONDS):
            self.tick()

    def start(self) -> None:
        if self._thread is not None or self._stop.is_set():
            raise RuntimeError("monitor already started")
        self.tick("START")
        self._thread = Thread(target=self._run, name="MLA-longrun-receipts", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # Stop can be invoked by more than one cleanup path. Emit STOP once;
        # a duplicate STOP would poison later previous-session recovery.
        with self._stop_lock:
            if self._stopped:
                return
            self._stop.set()
            if self._thread is not None:
                self._thread.join(timeout=5.0)
                if not self._thread.is_alive():
                    self.tick("STOP")
            self._stopped = True

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
                    "previous_session": (dict(self._previous_session)
                                         if self._previous_session is not None else None),
                    "system_ram_mb": visible(reading.ram_mb, 262144),
                    "process_ram_mb": self._process_ram_mb,
                    "process_ram_peak_mb": self._peak_process_ram_mb,
                    "cpu_percent": visible(reading.cpu_percent, 100),
                    "vram_mb": self._gpu_vram.used_mb if self._gpu_vram else None,
                    "vram_total_mb": self._gpu_vram.total_mb if self._gpu_vram else None,
                    "vram_scope": self._gpu_vram.scope if self._gpu_vram else None,
                    "temperature_c": None}
