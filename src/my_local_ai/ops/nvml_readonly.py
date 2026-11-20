"""Optional Windows NVIDIA GPU-wide VRAM telemetry; local, unprivileged, unverified.

Does not measure VRAM attributable to MLA/Ollama, and cannot certify P2 or F18.
The NVML DLL is loaded from Windows System32 only, never from the CWD/PATH.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import math
import os


@dataclass(frozen=True)
class NvidiaVramReading:
    used_mb: float
    total_mb: float
    scope: str = "NVIDIA_GPU_0_GLOBAL_UNATTESTED"


class _NvmlMemory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong),
                ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong)]


def _read_nvml(lib) -> NvidiaVramReading | None:
    """Read the first NVIDIA GPU; driver/permissions failure yields unknown."""
    lib.nvmlInit_v2.restype = ctypes.c_int
    lib.nvmlDeviceGetCount_v2.argtypes = [ctypes.POINTER(ctypes.c_uint)]
    lib.nvmlDeviceGetCount_v2.restype = ctypes.c_int
    lib.nvmlDeviceGetHandleByIndex_v2.argtypes = [
        ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
    lib.nvmlDeviceGetHandleByIndex_v2.restype = ctypes.c_int
    lib.nvmlDeviceGetMemoryInfo.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_NvmlMemory)]
    lib.nvmlDeviceGetMemoryInfo.restype = ctypes.c_int
    lib.nvmlShutdown.restype = ctypes.c_int
    if lib.nvmlInit_v2() != 0:
        return None
    try:
        count = ctypes.c_uint()
        if lib.nvmlDeviceGetCount_v2(ctypes.byref(count)) != 0 or count.value < 1:
            return None
        device = ctypes.c_void_p()
        if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(device)) != 0 or not device.value:
            return None
        info = _NvmlMemory()
        if lib.nvmlDeviceGetMemoryInfo(device, ctypes.byref(info)) != 0:
            return None
        total, used = info.total, info.used
        if not (0 < total <= 128 * 1024 ** 3 and 0 <= used <= total):
            return None
        used_mb, total_mb = round(used / 1048576, 2), round(total / 1048576, 2)
        if not (math.isfinite(used_mb) and math.isfinite(total_mb)):
            return None
        return NvidiaVramReading(used_mb=used_mb, total_mb=total_mb)
    finally:
        lib.nvmlShutdown()


def sample_nvidia_vram() -> NvidiaVramReading | None:
    """A single read-only NVML query, with no install, shell, egress or fallback."""
    if os.name != "nt":
        return None
    try:
        # LOAD_LIBRARY_SEARCH_SYSTEM32 prevents untrusted local DLL hijacking.
        driver = ctypes.WinDLL("nvml.dll", winmode=0x00000800)
        return _read_nvml(driver)
    except (OSError, AttributeError, TypeError, ValueError, OverflowError):
        return None
