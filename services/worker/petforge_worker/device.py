from __future__ import annotations

import ctypes
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass

_GIB = 1024**3


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    os_name: str
    architecture: str
    total_ram_bytes: int
    available_ram_bytes: int
    gpu_name: str | None
    gpu_memory_bytes: int | None
    gpu_driver_version: str | None
    cpu_reference_supported: bool
    unsupported_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["unsupported_reasons"] = list(self.unsupported_reasons)
        return payload


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _memory_status() -> tuple[int, int]:
    """Return physical total/available bytes without importing an ML runtime."""
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys), int(status.ullAvailPhys)
    except (AttributeError, OSError):
        pass
    return 0, 0


def peak_working_set_bytes() -> int:
    """Return this process's Windows peak working set, or zero when unavailable."""
    try:
        from ctypes import wintypes

        class _ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_process_memory_info.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        if get_process_memory_info(process, ctypes.byref(counters), counters.cb):
            return int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError, ImportError):
        pass
    return 0


def _query_nvidia_gpu() -> tuple[str, int, str] | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None

    first_line = result.stdout.splitlines()[0]
    parts = [part.strip() for part in first_line.split(",", maxsplit=2)]
    if len(parts) != 3:
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(MiB|MB|GiB|GB)", parts[1], re.IGNORECASE)
    if match is None:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = 1024**2 if unit in {"mib", "mb"} else 1024**3
    return parts[0], int(value * multiplier), parts[2]


def _canonical_architecture(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"amd64", "x86_64", "x64"}:
        return "x86_64"
    if normalized in {"arm64", "aarch64"}:
        return "arm64"
    return normalized or "unknown"


def probe_device(check_gpu: bool = False) -> DeviceProfile:
    """Probe basic Windows CPU/RAM support; query NVIDIA only on explicit request."""
    os_name = platform.system()
    architecture = _canonical_architecture(platform.machine())
    total_ram_bytes, available_ram_bytes = _memory_status()
    reasons: list[str] = []

    if os_name != "Windows":
        reasons.append(f"unsupported_os:{os_name.lower() or 'unknown'}")
    if architecture != "x86_64":
        reasons.append(f"unsupported_architecture:{architecture}")
    if total_ram_bytes == 0:
        reasons.append("memory_probe_failed")
    elif total_ram_bytes < 16 * _GIB:
        reasons.append("ram_below_16_gib_reference")

    cpu_reference_supported = not reasons
    gpu_name = None
    gpu_memory_bytes = None
    gpu_driver_version = None
    if check_gpu:
        gpu = _query_nvidia_gpu()
        if gpu is None:
            reasons.append("nvidia_gpu_not_detected")
        else:
            gpu_name, gpu_memory_bytes, gpu_driver_version = gpu

    return DeviceProfile(
        os_name=os_name or "unknown",
        architecture=architecture,
        total_ram_bytes=total_ram_bytes,
        available_ram_bytes=available_ram_bytes,
        gpu_name=gpu_name,
        gpu_memory_bytes=gpu_memory_bytes,
        gpu_driver_version=gpu_driver_version,
        cpu_reference_supported=cpu_reference_supported,
        unsupported_reasons=tuple(reasons),
    )
