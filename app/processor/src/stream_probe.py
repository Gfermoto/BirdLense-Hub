"""Probe live/file/RTSP streams for width, height, and FPS (SOTA-02 / #493)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping

logger = logging.getLogger(__name__)

ProbeSource = str  # ffprobe | opencv | measured | config


@dataclass(frozen=True)
class StreamCapabilities:
    """Discovered stream geometry and timing."""

    width: int
    height: int
    fps: float
    source: ProbeSource = "unknown"
    probe_url: str | None = None

    @property
    def main_size(self) -> tuple[int, int]:
        return (int(self.width), int(self.height))


def _probe_backend_preference() -> str:
    raw = (os.environ.get("BIRDLENSE_STREAM_PROBE") or "auto").strip().lower()
    if raw in ("ffprobe", "opencv", "auto"):
        return raw
    return "auto"


def _parse_fps_value(raw: Any) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        v = float(raw)
        return v if v > 0.5 else 0.0
    s = str(raw).strip()
    if not s or s in ("0/0", "N/A"):
        return 0.0
    if "/" in s:
        try:
            frac = Fraction(s)
            v = float(frac)
            return v if v > 0.5 else 0.0
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        v = float(s)
        return v if v > 0.5 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def probe_stream_ffprobe(
    url: str,
    *,
    timeout_sec: float = 15.0,
) -> StreamCapabilities | None:
    """Probe stream via ffprobe (RTSP, file, http)."""
    if not url or not _ffprobe_available():
        return None
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,avg_frame_rate",
        "-of",
        "json",
        url,
    ]
    try:
        run = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(3.0, float(timeout_sec)),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("ffprobe failed for %s: %s", url[:80], exc)
        return None
    if run.returncode != 0:
        logger.debug("ffprobe exit %s: %s", run.returncode, (run.stderr or "")[:200])
        return None
    try:
        payload = json.loads(run.stdout or "{}")
    except json.JSONDecodeError:
        return None
    streams = payload.get("streams") or []
    if not streams:
        return None
    st = streams[0]
    try:
        w = int(st.get("width") or 0)
        h = int(st.get("height") or 0)
    except (TypeError, ValueError):
        w, h = 0, 0
    fps = _parse_fps_value(st.get("avg_frame_rate"))
    if fps <= 0.5:
        fps = _parse_fps_value(st.get("r_frame_rate"))
    if w <= 0 or h <= 0:
        return None
    return StreamCapabilities(
        width=max(1, w),
        height=max(1, h),
        fps=max(1.0, fps) if fps > 0.5 else 0.0,
        source="ffprobe",
        probe_url=url,
    )


def probe_stream_opencv(
    url: str,
    *,
    measure_frames: int = 15,
    timeout_sec: float = 20.0,
) -> StreamCapabilities | None:
    """OpenCV probe: frame size + optional measured FPS."""
    import cv2

    if not url:
        return None
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        return None
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps_prop = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = fps_prop if fps_prop > 0.5 else 0.0
        if w <= 0 or h <= 0:
            ret, frame = cap.read()
            if ret and frame is not None and getattr(frame, "size", 0) > 0:
                h, w = int(frame.shape[0]), int(frame.shape[1])
        if w <= 0 or h <= 0:
            return None
        if fps <= 0.5 and measure_frames > 0:
            fps = _measure_capture_fps(cap, max_frames=measure_frames, timeout_sec=timeout_sec)
            source: ProbeSource = "measured" if fps > 0.5 else "opencv"
        else:
            source = "opencv"
        return StreamCapabilities(
            width=max(1, w),
            height=max(1, h),
            fps=max(1.0, fps) if fps > 0.5 else 0.0,
            source=source,
            probe_url=url,
        )
    finally:
        cap.release()


def _measure_capture_fps(cap: Any, *, max_frames: int = 15, timeout_sec: float = 20.0) -> float:
    """Estimate FPS by decoding ``max_frames`` frames."""

    n = max(3, int(max_frames))
    started = time.monotonic()
    count = 0
    while count < n:
        if time.monotonic() - started > timeout_sec:
            break
        ret, _ = cap.read()
        if not ret:
            break
        count += 1
    elapsed = time.monotonic() - started
    if count < 2 or elapsed <= 0.01:
        return 0.0
    return count / elapsed


def probe_stream_url(
    url: str,
    *,
    prefer: str | None = None,
    timeout_sec: float = 15.0,
) -> StreamCapabilities | None:
    """Probe URL: ffprobe → OpenCV (per ``BIRDLENSE_STREAM_PROBE``)."""
    if not (url or "").strip():
        return None
    mode = (prefer or _probe_backend_preference()).strip().lower()
    if mode == "opencv":
        return probe_stream_opencv(url, timeout_sec=timeout_sec)
    if mode == "ffprobe":
        cap = probe_stream_ffprobe(url, timeout_sec=timeout_sec)
        if cap is not None:
            return cap
        return probe_stream_opencv(url, timeout_sec=timeout_sec)
    cap = probe_stream_ffprobe(url, timeout_sec=timeout_sec)
    if cap is not None and cap.fps > 0.5:
        return cap
    opencv_cap = probe_stream_opencv(url, timeout_sec=timeout_sec)
    if opencv_cap is None:
        return cap
    if cap is None:
        return opencv_cap
    fps = cap.fps if cap.fps > 0.5 else opencv_cap.fps
    source = cap.source if cap.fps > 0.5 else opencv_cap.source
    return StreamCapabilities(
        width=cap.width,
        height=cap.height,
        fps=fps,
        source=source,
        probe_url=url,
    )


def probe_video_file(path: str, **kwargs: Any) -> StreamCapabilities | None:
    """Probe local video file."""
    p = (path or "").strip()
    if not p or not os.path.isfile(p):
        return None
    return probe_stream_url(p, **kwargs)


def attach_stream_capabilities(media_source: Any, caps: StreamCapabilities | None) -> None:
    """Store probe on media source for ``resolve_stream_fps`` / letterbox."""
    if media_source is None or caps is None:
        return
    try:
        media_source.stream_capabilities = caps
    except Exception:
        logger.debug("could not attach stream_capabilities", exc_info=True)
    for attr, val in (
        ("source_fps", caps.fps),
        ("_source_fps", caps.fps),
    ):
        if val > 0.5:
            try:
                setattr(media_source, attr, float(val))
            except Exception:
                pass


def get_stream_capabilities(media_source: Any | None) -> StreamCapabilities | None:
    if media_source is None:
        return None
    caps = getattr(media_source, "stream_capabilities", None)
    return caps if isinstance(caps, StreamCapabilities) else None


def _cfg_get(cfg: Mapping[str, Any], key: str, default: Any = None) -> Any:
    raw = cfg.get(key)
    if raw is not None:
        return raw
    parts = key.split(".")
    cur: Any = cfg
    for part in parts:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def parse_configured_video_size(runtime_cfg: Mapping[str, Any]) -> tuple[int, int] | None:
    """Legacy fixed WxH when ``force_recording_resolution`` and both dimensions > 0."""
    try:
        vw = int(_cfg_get(runtime_cfg, "video.video_width") or 0)
        vh = int(_cfg_get(runtime_cfg, "video.video_height") or 0)
    except (TypeError, ValueError):
        return None
    if vw > 0 and vh > 0:
        return (vw, vh)
    return None


def force_recording_resolution(runtime_cfg: Mapping[str, Any]) -> bool:
    """Legacy override: fixed config WxH wins over stream probe."""
    raw = _cfg_get(runtime_cfg, "video.force_recording_resolution", False)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


def resolve_main_size(
    runtime_cfg: Mapping[str, Any],
    probe: StreamCapabilities | None = None,
) -> tuple[int, int]:
    """Main/record WxH: per-stream probe; config only when ``force_recording_resolution``."""
    configured = parse_configured_video_size(runtime_cfg)
    if force_recording_resolution(runtime_cfg) and configured is not None:
        return configured
    if probe and probe.width > 0 and probe.height > 0:
        return (int(probe.width), int(probe.height))
    if configured is not None and not force_recording_resolution(runtime_cfg):
        logger.debug(
            "ignoring video.video_width/height without force_recording_resolution "
            "(use per-camera stream probe or set force_recording_resolution for file-replay)",
        )
    raise ValueError(
        "stream probe failed; set video.force_recording_resolution with video_width/height "
        "for offline file-replay, or ensure ffprobe/OpenCV can read the stream",
    )


def probe_go2rtc_record_streams(
    runtime_cfg: Mapping[str, Any],
) -> list[tuple[str, StreamCapabilities]]:
    """Probe every configured camera main/record stream (config order)."""
    go2rtc_url = (_cfg_get(runtime_cfg, "video.go2rtc_url") or "").strip()
    if not go2rtc_url:
        return []
    cameras = _cfg_get(runtime_cfg, "video.cameras") or []
    if not isinstance(cameras, list) or not cameras:
        return []
    try:
        from sources.go2rtc_stream_source import _build_stream_url
    except Exception:
        logger.debug("go2rtc record stream probe import failed", exc_info=True)
        return []

    username = _cfg_get(runtime_cfg, "video.go2rtc_username")
    password = _cfg_get(runtime_cfg, "video.go2rtc_password")
    out: list[tuple[str, StreamCapabilities]] = []
    for idx, cam in enumerate(cameras):
        if not isinstance(cam, Mapping):
            continue
        stream_name = (cam.get("stream_name") or "").strip()
        if not stream_name:
            continue
        cid = str(cam.get("id") or stream_name or f"camera_{idx + 1}").strip()
        try:
            record_url = _build_stream_url(
                go2rtc_url,
                stream_name,
                username=username,
                password=password,
            )
            caps = probe_stream_url(record_url)
        except Exception:
            logger.debug("go2rtc record probe failed camera=%s", cid, exc_info=True)
            caps = None
        if caps is not None:
            out.append((cid, caps))
    return out


def _probe_go2rtc_startup(runtime_cfg: Mapping[str, Any]) -> StreamCapabilities | None:
    """Probe all camera record streams; return first successful for global bootstrap WxH."""
    probes = probe_go2rtc_record_streams(runtime_cfg)
    if not probes:
        return None
    return probes[0][1]


def probe_processor_startup(
    runtime_cfg: Mapping[str, Any],
    *,
    input_path: str | None = None,
    capture_url: str | None = None,
) -> StreamCapabilities | None:
    """Best-effort probe at processor bootstrap (file CLI, detect RTSP, or go2rtc record)."""
    if input_path:
        return probe_video_file(input_path)
    if capture_url:
        return probe_stream_url(capture_url)
    source = (_cfg_get(runtime_cfg, "video.source") or "go2rtc").strip().lower()
    if source == "file":
        fp = (_cfg_get(runtime_cfg, "video.file_path") or "").strip()
        if fp and os.path.isfile(fp):
            return probe_video_file(fp)
    if source == "go2rtc":
        return _probe_go2rtc_startup(runtime_cfg)
    return None


def publish_probe_gauges(caps: StreamCapabilities | None) -> None:
    if caps is None:
        return
    try:
        from processor_runtime_stats import set_gauge

        set_gauge("stream_probe_width", int(caps.width))
        set_gauge("stream_probe_height", int(caps.height))
        set_gauge("stream_probe_fps", round(float(caps.fps), 3) if caps.fps > 0 else 0)
        set_gauge("stream_probe_source", caps.source)
    except Exception:
        logger.debug("publish_probe_gauges failed", exc_info=True)
