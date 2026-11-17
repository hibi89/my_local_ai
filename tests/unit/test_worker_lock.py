"""Synthetic lock and budget adversarial tests; never start Ollama."""
from pathlib import Path
import tempfile
import unittest
import os
from unittest.mock import patch
from my_local_ai.ax_runtime import worker_lock

from my_local_ai.ax_runtime.worker_lock import OneModelLock, ModelLockBusy, ModelLockUnsafe
from my_local_ai.ax_runtime.budgets import ModelBudget, BudgetGuard, BudgetExceeded

class WorkerLockTests(unittest.TestCase):
    def test_one_model_only_and_epoch_increases(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = OneModelLock(folder), OneModelLock(folder)
            one = a.acquire()
            with self.assertRaises(ModelLockBusy):
                b.acquire()
            a.release(one)
            two = b.acquire()
            self.assertGreater(two.generation, one.generation)
            b.release(two)

    def test_stale_release_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            guard = OneModelLock(folder)
            old = guard.acquire()
            guard.release(old)
            new = guard.acquire()
            with self.assertRaises(ModelLockUnsafe):
                guard.release(old)
            guard.release(new)

    def test_corrupt_epoch_does_not_recover_unsafely(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "my_local_ai.model.lock"
            path.write_text("INVALID", encoding="ascii")
            with self.assertRaises(ModelLockUnsafe):
                OneModelLock(folder).acquire()
            self.assertEqual(path.read_text(encoding="ascii"), "INVALID")

    def test_symlink_lock_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target"
            target.write_text("0")
            alias = Path(folder) / "my_local_ai.model.lock"
            try:
                alias.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported in this environment")
            with self.assertRaises(ModelLockUnsafe):
                OneModelLock(folder).acquire()

class BudgetTests(unittest.TestCase):
    def test_reject_invalid_caps(self):
        for cap in (-1, 0, 101, True):
            with self.assertRaises(ValueError):
                ModelBudget(max_calls=cap)

    def test_call_count_and_no_replenishment(self):
        limit = BudgetGuard(ModelBudget(max_calls=2))
        self.assertEqual(limit.reserve_call(), 1)
        self.assertEqual(limit.reserve_call(), 2)
        with self.assertRaises(BudgetExceeded):
            limit.reserve_call()

    def test_timeout_is_fail_closed(self):
        time = [10.0]
        guard = BudgetGuard(ModelBudget(max_seconds=5), clock=lambda: time[0])
        guard.reserve_call()
        time[0] = 15.01
        with self.assertRaises(BudgetExceeded):
            guard.reserve_call()

    def test_budget_dimension_and_nonfinite(self):
        guard = BudgetGuard(ModelBudget())
        guard.check(context_tokens=8192, changed_files=16)
        for kwargs in ({"ram_mb": float("nan")}, {"disk_mb": -1}, {"changed_files": 17},
                       {"output_bytes": 3000000}, {"context_tokens": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(BudgetExceeded):
                guard.check(**kwargs)

if __name__ == "__main__":
    unittest.main()


class BudgetClockSafetyTests(unittest.TestCase):
    def test_nan_or_backwards_clock_never_extends_budget(self):
        for bad in (float("nan"), float("inf"), True):
            with self.subTest(clock=bad):
                with self.assertRaises(BudgetExceeded):
                    BudgetGuard(ModelBudget(), clock=lambda: bad)
        ticks = [10.0]
        budget = BudgetGuard(ModelBudget(), clock=lambda: ticks[0])
        budget.reserve_call()
        ticks[0] = 9.9
        with self.assertRaises(BudgetExceeded):
            budget.reserve_call()
        with self.assertRaises(BudgetExceeded):
            budget.check()

    def test_clock_nan_after_start_rejected_before_any_call(self):
        ticks = [1.0]
        budget = BudgetGuard(ModelBudget(), clock=lambda: ticks[0])
        ticks[0] = float("nan")
        with self.assertRaises(BudgetExceeded):
            budget.reserve_call()


class LockReplacementRaceTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "synthetic path replacement requires POSIX")
    def test_lock_path_replacement_after_os_lock_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            lockfile = Path(folder) / "my_local_ai.model.lock"
            original = worker_lock._os_lock
            def swap_after_lock(handle):
                original(handle)
                lockfile.unlink()
                lockfile.write_text("0", encoding="ascii")
            with patch.object(worker_lock, "_os_lock", side_effect=swap_after_lock):
                with self.assertRaises(ModelLockUnsafe):
                    OneModelLock(folder).acquire()
            self.assertEqual(lockfile.read_text(encoding="ascii"), "0")



class DurableFencingEpochTests(unittest.TestCase):
    def test_existing_empty_file_never_resets_epoch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp) / "my_local_ai.model.lock"
            path.write_bytes(b"")
            with self.assertRaises(ModelLockUnsafe):
                OneModelLock(tmp).acquire()
            self.assertEqual(path.read_bytes(),b"")

    def test_new_file_still_initializes_and_releases_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock=OneModelLock(tmp)
            lease=lock.acquire()
            self.assertEqual(lease.generation,1)
            lock.release(lease)
            self.assertEqual((Path(tmp)/"my_local_ai.model.lock").read_text(),"1")
            resumed=lock.acquire()
            self.assertEqual(resumed.generation,2)
            lock.release(resumed)


class DiscreteBudgetSafetyTests(unittest.TestCase):
    def test_fractional_or_boolean_counts_never_granted(self):
        g=BudgetGuard(ModelBudget())
        for changes in (
            {"changed_files":1.5}, {"context_tokens":20.3},
            {"output_bytes":1.2}, {"changed_files":True},
            {"context_tokens":"4"},
        ):
            with self.subTest(changes=changes),self.assertRaises(BudgetExceeded):
                g.check(**changes)

    def test_float_memory_disk_metrics_remain_usable(self):
        BudgetGuard(ModelBudget()).check(ram_mb=1200.5,disk_mb=2.5)
