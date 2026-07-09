"""Снимок CPU/RAM/диск/GPU без обращения к БД посетителей (#265)."""

from __future__ import annotations

import os
import subprocess

import psutil

from app_config.app_config import app_config
from encoding_utils import normalize_video_encoding


def _normalize_encoding_setting(raw: str | None) -> str:
    return normalize_video_encoding(raw, "jetson")


def _platform_id() -> str:
    return (os.environ.get("BIRDLENSE_PLATFORM") or "orin").strip().lower()


def _nvidia_gpu_percent() -> float | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0:
            return None
        line = (result.stdout or "").strip().splitlines()[0].strip()
        if not line or line.upper() == "N/A":
            return None
        val = float(line)
        return round(val, 1) if 0 <= val <= 100 else None
    except (OSError, ValueError, subprocess.TimeoutExpired, IndexError):
        return None


def collect_live_system_metrics(app):
    """Мгновенный снимок: CPU, память, диск, GPU."""
    try:
        cpu_interval = max(0.0, float(app_config.get("system_metrics.cpu_sample_interval_seconds") or 0.0))
    except (TypeError, ValueError):
        cpu_interval = 0.0
    cpu_percent = psutil.cpu_percent(interval=cpu_interval)
    memory = psutil.virtual_memory()
    memory_total_gb = round(memory.total / (1024**3), 1)
    memory_used_gb = round(memory.used / (1024**3), 1)
    memory_percent = memory.percent
    disk = psutil.disk_usage("/")
    disk_total_gb = round(disk.total / (1024**3), 1)
    disk_used_gb = round(disk.used / (1024**3), 1)
    disk_percent = disk.percent

    gpu_percent = None
    for path in ("/sys/class/drm/card0/device/gpu_busy_percent", "/sys/class/drm/card0/device/utilization"):
        try:
            with open(path) as f:
                raw = f.read().strip()
            val = int(raw)
            if 0 <= val <= 100:
                gpu_percent = val
            elif 0 <= val <= 255:
                gpu_percent = round(100 * val / 255)
            if gpu_percent is not None:
                break
        except (OSError, ValueError):
            continue
    encoding_setting = _normalize_encoding_setting(app_config.get("video.encoding"))
    if gpu_percent is None:
        gpu_percent = _nvidia_gpu_percent()

    return {
        "cpu": {"percent": cpu_percent},
        "memory": {
            "total": memory_total_gb,
            "used": memory_used_gb,
            "percent": memory_percent,
            "total_bytes": memory.total,
            "used_bytes": memory.used,
        },
        "disk": {"total": disk_total_gb, "used": disk_used_gb, "percent": disk_percent},
        "encoding": encoding_setting,
        "gpu_percent": gpu_percent,
    }
