"""Synthetic monitor evidence only; not real Windows, suspend or 24-hour proof."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from my_local_ai.ax_runtime.longrun_monitor import LongrunMonitor
from my_local_ai.ops.resource_monitor import ResourceReading


class Clock:
    def __init__(self):
        self.mono = 1000.0
        self.wall = 2000.0


class MonitorTests(unittest.TestCase):
    def test_start_gap_stop_reopen_and_bounded_redaction(self):
        with TemporaryDirectory() as path:
            root = Path(path)
            t = Clock()
            def reading(*, previous_cpu=None):
                return ResourceReading(2000.0, None, None, 11.2,
                                       source="LOCAL_READ_ONLY_UNATTESTED"), None
            monitor = LongrunMonitor(root, clock=lambda: t.mono,
                                     wall=lambda: t.wall, sampler=reading,
                                     process_sampler=lambda: 123.5)
            monitor.tick("START")
            t.mono += 61
            t.wall += 61
            monitor.tick()
            t.mono += 700
            t.wall += 1300
            monitor.tick()
            monitor.tick("STOP")
            snap = monitor.snapshot()
            self.assertEqual(snap["clock_or_sampling_gaps"], 1)
            self.assertFalse(snap["real_24h_accepted"])
            self.assertIsNone(snap["vram_mb"])
            self.assertEqual(snap["verification"], "NOT_RUN")
            self.assertEqual(snap["process_ram_mb"], 123.5)
            self.assertEqual(snap["process_ram_peak_mb"], 123.5)
            with sqlite3.connect(root / ".mla-timing.sqlite3") as db:
                self.assertEqual(db.execute("SELECT count(*) FROM longrun_receipts").fetchone()[0], 4)
                self.assertEqual(db.execute("SELECT event FROM longrun_receipts ORDER BY id DESC LIMIT 1").fetchone()[0], "STOP")
                self.assertEqual(db.execute("SELECT count(*) FROM longrun_process_ram").fetchone()[0], 4)
            reopened = LongrunMonitor(root, clock=lambda: t.mono,
                                      wall=lambda: t.wall, sampler=reading)
            reopened.tick("START")
            self.assertIs(reopened.snapshot()["previous_session_unclosed"], False)
            interrupted = LongrunMonitor(root, clock=lambda: t.mono,
                                         wall=lambda: t.wall, sampler=reading)
            interrupted.tick("START")
            self.assertIs(interrupted.snapshot()["previous_session_unclosed"], True)

    def test_storage_failure_never_claims_proof_or_starts_worker(self):
        with TemporaryDirectory() as path:
            root = Path(path)
            try:
                (root / ".mla-timing.sqlite3").symlink_to(root / "missing")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            monitor = LongrunMonitor(root)
            monitor.tick("START")
            self.assertEqual(monitor.snapshot()["status"], "EVIDENCE_UNAVAILABLE")
            self.assertEqual(monitor.snapshot()["samples"], 0)

    def test_unavailable_or_invalid_process_sensor_never_invents_ram(self):
        with TemporaryDirectory() as path:
            root = Path(path)
            values = iter([float("nan"), -42.0, 104.25])
            monitor = LongrunMonitor(root, process_sampler=lambda: next(values))
            monitor.tick("START")
            self.assertIsNone(monitor.snapshot()["process_ram_mb"])
            monitor.tick()
            self.assertIsNone(monitor.snapshot()["process_ram_mb"])
            monitor.tick()
            self.assertEqual(monitor.snapshot()["process_ram_peak_mb"], 104.25)
            self.assertFalse(monitor.snapshot()["real_24h_accepted"])
            with sqlite3.connect(root / ".mla-timing.sqlite3") as db:
                self.assertEqual(db.execute("SELECT count(*) FROM longrun_receipts").fetchone()[0], 3)
                self.assertEqual(db.execute("SELECT count(*) FROM longrun_process_ram").fetchone()[0], 1)

    def test_reject_unrecognized_event(self):
        with TemporaryDirectory() as path:
            monitor = LongrunMonitor(Path(path))
            with self.assertRaises(ValueError):
                monitor.tick("EXECUTE_CODE")


if __name__ == "__main__":
    unittest.main()
