"""Synthetic NVML call-contract tests; no real GPU or P2 acceptance."""
import ctypes
import os
import unittest

from my_local_ai.ops.nvml_readonly import (
    _NvmlMemory, _read_nvml, sample_nvidia_vram,
)


class NativeCall:
    def __init__(self, callback):
        self.callback = callback
        self.restype = None
        self.argtypes = None

    def __call__(self, *args):
        return self.callback(*args)


class FakeNvml:
    def __init__(self, *, used=512, total=4096, memory_result=0):
        self.shutdown_count = 0
        self.nvmlInit_v2 = NativeCall(lambda: 0)
        self.nvmlDeviceGetCount_v2 = NativeCall(
            lambda ptr: self._count(ptr))
        self.nvmlDeviceGetHandleByIndex_v2 = NativeCall(
            lambda index, ptr: self._handle(index, ptr))
        self.nvmlDeviceGetMemoryInfo = NativeCall(
            lambda device, ptr: self._memory(ptr, used, total, memory_result))
        self.nvmlShutdown = NativeCall(self._shutdown)

    @staticmethod
    def _count(ptr):
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint)).contents.value = 1
        return 0

    @staticmethod
    def _handle(index, ptr):
        if index != 0:
            return 1
        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p)).contents.value = 1234
        return 0

    @staticmethod
    def _memory(ptr, used, total, result):
        info = ctypes.cast(ptr, ctypes.POINTER(_NvmlMemory)).contents
        info.used = int(used * 1048576)
        info.total = int(total * 1048576)
        info.free = max(0, info.total - info.used)
        return result

    def _shutdown(self):
        self.shutdown_count += 1
        return 0


class VramTests(unittest.TestCase):
    def test_gpu_wide_memory_and_shutdown(self):
        fake = FakeNvml()
        result = _read_nvml(fake)
        self.assertEqual(result.used_mb, 512)
        self.assertEqual(result.total_mb, 4096)
        self.assertEqual(result.scope, "NVIDIA_GPU_0_GLOBAL_UNATTESTED")
        self.assertEqual(fake.shutdown_count, 1)

    def test_native_unavailable_or_unreasonable_never_fabricates_memory(self):
        for kwargs in ({"memory_result": 5}, {"used": 5000, "total": 4096},
                       {"total": 0}, {"total": 131073}):
            with self.subTest(kwargs=kwargs):
                fake = FakeNvml(**kwargs)
                self.assertIsNone(_read_nvml(fake))
                self.assertEqual(fake.shutdown_count, 1)

    def test_failed_init_does_not_shutdown_uninitialized_driver(self):
        fake = FakeNvml()
        fake.nvmlInit_v2 = NativeCall(lambda: 1)
        self.assertIsNone(_read_nvml(fake))
        self.assertEqual(fake.shutdown_count, 0)

    @unittest.skipIf(os.name == "nt", "Windows driver may be present")
    def test_nonwindows_fails_closed(self):
        self.assertIsNone(sample_nvidia_vram())


if __name__ == "__main__":
    unittest.main()
