"""Снимок CPU/RAM/диск/GPU без обращения к БД посетителей (#265)."""

from __future__ import annotations

import os

import psutil

from app_config.app_config import app_config


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
    encoding_setting = (app_config.get("video.encoding") or "cpu").strip().lower()
    if encoding_setting not in ("cpu", "intel"):
        encoding_setting = "cpu"
    intel_gpu = encoding_setting == "intel" or os.path.exists("/dev/dri/renderD128")
    if gpu_percent is None and intel_gpu:
        try:
            from gpu_stats import get_intel_gpu_percent

            gpu_percent = get_intel_gpu_percent()
        except Exception as e:
            app.logger.warning("gpu_stats: %s", e)

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
