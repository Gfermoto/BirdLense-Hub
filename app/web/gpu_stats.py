"""
Intel GPU utilization — по образцу Frigate NVR.
1) intel_gpu_top -J (работает на Gen 1–11)
2) Fallback: DRM fdinfo (/proc/PID/fdinfo) для Gen 12+ (Alder Lake-N и новее)
"""

import glob
import json
import logging
import os
import subprocess
import time

_log = logging.getLogger("gpu_stats")

_CACHE_PATH = "/tmp/.birdlense_gpu_stats_cache"
_MIN_DELTA_NS = 100_000_000  # 100ms
# intel_gpu_top в Docker: PMU / запись в /tmp — одни и те же ошибки на каждый poll — душим до 1 раза в час.
_INTEL_GPU_TOP_BENIGN_STDERR_SUPPRESS_S = 3600.0
_intel_gpu_top_benign_stderr_next_log_monotonic = 0.0


def _intel_gpu_top() -> float | None:
    """intel_gpu_top -J -o FILE -s 100. Frigate: (Render + Video) / 2."""
    out_path = "/tmp/birdlense_igt.json"
    try:
        result = subprocess.run(
            "timeout 3 intel_gpu_top -J -o " + out_path + " -s 100",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        rc = result.returncode
        stderr = (result.stderr or "")[:200]
        if rc not in (0, 124):
            global _intel_gpu_top_benign_stderr_next_log_monotonic
            sl = stderr.lower()
            pmu_denied = "pmu" in sl and "permission denied" in sl
            output_file_denied = "permission denied" in sl and (
                "output file" in sl or "failed to open" in sl or "open output" in sl
            )
            benign = pmu_denied or output_file_denied
            now_m = time.monotonic()
            if benign:
                # rc=1 часто при этом всё же пишет JSON в -o FILE — душим только лог.
                if now_m >= _intel_gpu_top_benign_stderr_next_log_monotonic:
                    _intel_gpu_top_benign_stderr_next_log_monotonic = now_m + _INTEL_GPU_TOP_BENIGN_STDERR_SUPPRESS_S
                    _log.warning("intel_gpu_top rc=%s stderr=%s", rc, stderr)
            else:
                _log.warning("intel_gpu_top rc=%s stderr=%s", rc, stderr)
        if not os.path.exists(out_path):
            _log.warning("intel_gpu_top: output file missing")
            return None
        with open(out_path) as f:
            out = f.read()
        if not out or len(out) < 100:
            return None
        # intel_gpu_top выводит несколько JSON подряд. Берём последний через raw_decode.
        decoder = json.JSONDecoder()
        data = None
        idx = 0
        while idx < len(out):
            while idx < len(out) and out[idx] in " \t\n\r":
                idx += 1
            if idx >= len(out):
                break
            try:
                data, end = decoder.raw_decode(out, idx)
                idx = end
            except json.JSONDecodeError:
                break
        if not data:
            return None
        engines = data.get("engines") or {}
        render = engines.get("Render/3D/0") or engines.get("Render/3D") or {}
        video = engines.get("Video/0") or engines.get("Video") or {}
        r = float(render.get("busy", 0) or 0)
        v = float(video.get("busy", 0) or 0)
        pct = (r + v) / 2.0
        return round(pct, 1) if 0 <= pct <= 100 else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, FileNotFoundError, OSError) as e:
        _log.warning("intel_gpu_top: %s", e)
        return None
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def _fdinfo_snapshot() -> tuple[int, int, int, str] | None:
    """Читает суммарные drm-engine-render и drm-engine-video из /proc/*/fdinfo."""
    import time

    total_r, total_v = 0, 0
    driver = ""
    seen_pids = set()
    for fdinfo_path in glob.glob("/proc/[0-9]*/fdinfo/*"):
        try:
            pid = fdinfo_path.split("/")[2]
            with open(fdinfo_path) as f:
                content = f.read()
            if "drm-driver:" not in content:
                continue
            for line in content.splitlines():
                if line.startswith("drm-driver:"):
                    driver = line.split(":", 1)[1].strip()
                    break
            r = v = 0
            if driver == "i915":
                for line in content.splitlines():
                    if line.startswith("drm-engine-render:"):
                        r = int(line.split(":", 1)[1].strip().split()[0])
                    elif line.startswith("drm-engine-video:"):
                        v = int(line.split(":", 1)[1].strip().split()[0])
            elif driver == "xe":
                for line in content.splitlines():
                    if line.startswith("drm-cycles-rcs:"):
                        r = int(line.split(":", 1)[1].strip().split()[0])
                    elif line.startswith("drm-cycles-vcs:"):
                        v = int(line.split(":", 1)[1].strip().split()[0])
            total_r += r
            total_v += v
            seen_pids.add(pid)
        except (OSError, ValueError):
            continue
    if driver and seen_pids:
        return (int(time.time() * 1e9), total_r, total_v, driver)
    return None


def _fdinfo_percent() -> float | None:
    """DRM fdinfo: сравнение с кэшем, (Render+Video)/2 как proxy загрузки."""
    snap = _fdinfo_snapshot()
    if not snap:
        return None
    now_ns, total_r, total_v, driver = snap

    prev_ns = prev_r = prev_v = 0
    prev_driver = ""
    try:
        with open(_CACHE_PATH) as f:
            parts = f.read().split()
            if len(parts) >= 4:
                prev_ns, prev_r, prev_v = int(parts[0]), int(parts[1]), int(parts[2])
                prev_driver = parts[3]
    except (OSError, ValueError, IndexError):
        pass

    try:
        with open(_CACHE_PATH, "w") as f:
            f.write(f"{now_ns} {total_r} {total_v} {driver}\n")
    except OSError:
        pass

    if prev_ns == 0 or now_ns - prev_ns < _MIN_DELTA_NS or prev_driver != driver:
        return None

    delta_ns = now_ns - prev_ns
    dr = max(0, total_r - prev_r)
    dv = max(0, total_v - prev_v)
    r_pct = (dr / delta_ns) * 100 if delta_ns > 0 else 0
    v_pct = (dv / delta_ns) * 100 if delta_ns > 0 else 0
    pct = (r_pct + v_pct) / 2.0
    return round(pct, 1) if 0 <= pct <= 100 else None


def get_intel_gpu_percent() -> float | None:
    """
    Загрузка Intel GPU в % (0–100).
    Сначала DRM fdinfo (быстро, Gen 12+). При неудаче — intel_gpu_top (Gen 1–11).
    """
    fdinfo_pct = _fdinfo_percent()
    if fdinfo_pct is not None:
        return fdinfo_pct
    pct = _intel_gpu_top()
    if pct is not None:
        return pct
    return None
