"""Local 24h numerical summary tests; these are NOT Owner/P2 acceptance."""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from my_local_ai.ax_runtime.longrun_monitor import LongrunMonitor
from my_local_ai.ops.nvml_readonly import NvidiaVramReading
from my_local_ai.ops.resource_monitor import ResourceReading


class Clock:
    def __init__(self):
        self.monotonic = 1000.0
        self.wall = 100000.0

    def advance(self, seconds: float):
        self.monotonic += seconds
        self.wall += seconds


def sample_reading(*, previous_cpu=None):
    return ResourceReading(4096.0, None, None, 15.0,
                           source="LOCAL_READ_ONLY_UNATTESTED"), None


def make_monitor(root, clock, *, process_ram=85.5, gpu_used=200.0):
    return LongrunMonitor(
        root, clock=lambda: clock.monotonic, wall=lambda: clock.wall,
        sampler=sample_reading, process_sampler=lambda: process_ram,
        gpu_sampler=lambda: NvidiaVramReading(gpu_used, 4096.0),
    )


class DigestTests(unittest.TestCase):
    def test_24h_current_and_prior_sessions_remain_unverified(self):
        with TemporaryDirectory() as directory:
            root, clock = Path(directory), Clock()
            first = make_monitor(root, clock)
            first.tick("START")
            clock.advance(60)
            first.tick()
            clock.advance(1)
            first.tick("STOP")
            second = make_monitor(root, clock, process_ram=185.5, gpu_used=800.0)
            second.tick("START")
            digest = second.snapshot()["observation_24h"]
            self.assertEqual(digest["window_seconds"], 86400)
            self.assertEqual(digest["recorded_samples"], 4)
            self.assertEqual(digest["recorded_sessions"], 2)
            self.assertEqual(digest["recorded_gaps"], 0)
            self.assertEqual(digest["recorded_span_seconds"], 61)
            self.assertEqual(digest["process_ram_peak_mb"], 185.5)
            self.assertEqual(digest["gpu0_global_vram_peak_mb"], 800.0)
            self.assertEqual(digest["verification"], "NOT_RUN")
            self.assertFalse(digest["real_24h_accepted"])
            self.assertEqual(second.snapshot()["status"], "LOCAL_UNATTESTED")
            digest["recorded_samples"] = -1
            self.assertEqual(second.snapshot()["observation_24h"]["recorded_samples"], 4)

    def test_only_last_24h_wall_receipts_and_detect_gaps(self):
        with TemporaryDirectory() as directory:
            root, clock = Path(directory), Clock()
            monitor = make_monitor(root, clock)
            monitor.tick("START")
            clock.advance(86401)
            monitor.tick("HEARTBEAT")
            observation = monitor.snapshot()["observation_24h"]
            self.assertEqual(observation["recorded_samples"], 1)
            self.assertEqual(observation["recorded_sessions"], 1)
            self.assertEqual(observation["recorded_gaps"], 1)
            self.assertEqual(observation["recorded_span_seconds"], 0)
            self.assertFalse(observation["retention_limit_reached"])
            self.assertFalse(observation["real_24h_accepted"])

    def test_tampered_receipts_fail_closed_without_new_db_write(self):
        with TemporaryDirectory() as directory:
            root, clock = Path(directory), Clock()
            monitor = make_monitor(root, clock)
            monitor.tick("START")
            with closing(sqlite3.connect(root / ".mla-timing.sqlite3")) as db, db:
                db.execute("UPDATE longrun_receipts SET gap = 9")
            clock.advance(60)
            monitor.tick()
            self.assertEqual(monitor.snapshot()["status"], "EVIDENCE_UNAVAILABLE")
            self.assertIsNone(monitor.snapshot()["observation_24h"])
            self.assertFalse(monitor.snapshot()["real_24h_accepted"])
            with closing(sqlite3.connect(root / ".mla-timing.sqlite3")) as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM longrun_receipts").fetchone()[0], 1
                )


if __name__ == "__main__":
    unittest.main()
