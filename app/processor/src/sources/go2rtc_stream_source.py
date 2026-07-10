"""
Go2RTC stream source for Orin (ARM64 Docker).
Reads video from RTSP/HLS URL (Go2RTC), supports auto-reconnect, recording via FFmpeg/GStreamer.
Encoding: jetson (GStreamer NVDEC/NVENC on Orin) or cpu (software fallback).
"""

import glob
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
from collections import deque

import cv2
import numpy as np


from .streaming_server import start_streaming_server

logger = logging.getLogger(__name__)


def _set_runtime_gauge(name: str, value) -> None:
    """Best-effort runtime diagnostics hook."""
    try:
        from processor_runtime_stats import set_gauge

        set_gauge(name, value)
    except Exception:
        logger.debug("runtime set_gauge %s failed", name, exc_info=True)


def _inc_runtime_counter(name: str, delta: int = 1) -> None:
    """Best-effort runtime diagnostics counter hook."""
    try:
        from processor_runtime_stats import inc_counter

        inc_counter(name, int(delta))
    except Exception:
        logger.debug("runtime inc_counter %s failed", name, exc_info=True)


def _ffmpeg_stderr_log_level(line: str) -> int:
    """Шумные строки прогресса/аудио — DEBUG, итоги и ошибки — INFO."""
    s = line.strip()
    if not s:
        return logging.DEBUG
    if "Queue input is backward in time" in s:
        return logging.DEBUG
    if "Last message repeated" in s:
        return logging.DEBUG
    if s.startswith("frame=") and "fps=" in s:
        return logging.DEBUG
    return logging.INFO


# FFmpeg печатает Input #0, rtsp, from 'rtsp://user:pass@host/...' — не логировать креды (#384).
_RTSP_URL_AUTH_RE = re.compile(
    r"(?P<proto>rtsp://)(?P<user>[^/@?#]+):(?P<pass>[^@]+)@",
    re.IGNORECASE,
)


def _sanitize_ffmpeg_stderr_line(line: str) -> str:
    """Redact user:password in rtsp:// URLs before logging (FFmpeg stderr echoes full Input URL)."""
    if "rtsp://" not in line and "RTSP://" not in line:
        return line
    return _RTSP_URL_AUTH_RE.sub(r"\1***:***@", line)


from encoding_utils import normalize_capture_backend as _normalize_capture_backend


def _capture_fallback_reason(
    *,
    requested_backend: str,
    encoding_mode: str,
    nvmpi_available: bool = False,
) -> str:
    """Classify fallback reason for capture backend telemetry."""
    rb = _normalize_capture_backend(requested_backend)
    enc = (encoding_mode or "cpu").strip().lower()
    if rb == "opencv":
        return "requested_opencv"
    if rb == "ffmpeg_nvmpi" and not nvmpi_available:
        return "nvmpi_unavailable"
    if rb == "auto" and enc == "jetson" and not nvmpi_available:
        return "auto_nvmpi_probe_failed"
    if rb == "auto" and enc == "cpu":
        return "auto_prefers_opencv_for_cpu_encoding"
    return "fallback_to_opencv"


def _ffmpeg_has_nvenc() -> bool:
    """Check if ffmpeg has h264_nvenc (NVIDIA NVENC, Orin Docker / desktop)."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-encoders"], capture_output=True, timeout=5,
        ).stdout.decode()
        return "h264_nvenc" in out
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _gst_jetson_h264_encoder() -> str | None:
    """GStreamer HW H.264 encoder for this Jetson generation (JP7: nvv4l2h264enc)."""
    for enc in ("nvv4l2h264enc", "omxh264enc"):
        try:
            out = subprocess.run(
                ["gst-inspect-1.0", enc],
                capture_output=True, timeout=5,
            )
            if out.returncode == 0:
                return enc
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
    return None


def _gst_jetson_record_available() -> bool:
    """GStreamer NVMM record path (L4T native Jetson, not generic CUDA Docker)."""
    try:
        out = subprocess.run(
            ["gst-inspect-1.0", "nvv4l2decoder"],
            capture_output=True, timeout=5,
        )
        if out.returncode != 0:
            return False
        return _gst_jetson_h264_encoder() is not None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _gst_nvdec_capture_available() -> bool:
    """True when nvv4l2decoder can decode live RTSP for detect/capture."""
    try:
        out = subprocess.run(
            ["gst-inspect-1.0", "nvv4l2decoder"],
            capture_output=True,
            timeout=5,
        )
        return out.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


# Process-wide sticky OpenCV window after NVDEC fail (survives source rebuild).
_NVDEC_OPENCV_COOLDOWN_UNTIL_MONO: float = 0.0


class _GstRtspNvdecCapture:
    """Minimal VideoCapture-like wrapper: RTSP → nvv4l2decoder → BGR frames."""

    def __init__(self, stream_url: str, *, latency_ms: int = 200):
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst, GLib

        Gst.init(None)
        self._Gst = Gst
        self._GLib = GLib
        safe_url = stream_url.replace("&", "%26").replace('"', "%22")
        desc = (
            f'rtspsrc location="{safe_url}" latency={int(latency_ms)} protocols=tcp ! '
            "rtph264depay ! h264parse ! nvv4l2decoder enable-max-performance=1 ! "
            "nvvidconv ! video/x-raw,format=BGRx ! "
            "appsink name=sink emit-signals=false sync=false max-buffers=1 drop=true"
        )
        self._pipe = Gst.parse_launch(desc)
        self._sink = self._pipe.get_by_name("sink")
        self._bus = self._pipe.get_bus()
        self._ctx = GLib.MainContext.default()
        self._fps = 0.0
        self._opened = False
        ret = self._pipe.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            self.release()
            return
        # Wait for first buffer (preroll / playing).
        deadline = time.perf_counter() + 8.0
        while time.perf_counter() < deadline:
            while self._ctx.pending():
                self._ctx.iteration(False)
            msg = self._bus.timed_pop_filtered(50 * Gst.MSECOND, Gst.MessageType.ANY)
            if msg is not None and msg.type == Gst.MessageType.ERROR:
                self.release()
                return
            sample = self._sink.emit("try-pull-sample", 100 * Gst.MSECOND)
            if sample is not None:
                self._opened = True
                # Keep first sample available via immediate re-pull after open — drop it.
                break
        if not self._opened:
            self.release()

    def isOpened(self) -> bool:
        return bool(self._opened)

    def set(self, _prop, _value) -> bool:
        return True

    def get(self, prop) -> float:
        if prop == cv2.CAP_PROP_FPS:
            return float(self._fps or 0.0)
        return 0.0

    def read(self):
        if not self._opened:
            return False, None
        Gst = self._Gst
        while self._ctx.pending():
            self._ctx.iteration(False)
        sample = self._sink.emit("try-pull-sample", 500 * Gst.MSECOND)
        if sample is None:
            return False, None
        buf = sample.get_buffer()
        caps = sample.get_caps().get_structure(0)
        w = int(caps.get_value("width"))
        h = int(caps.get_value("height"))
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return False, None
        try:
            arr = np.frombuffer(mapinfo.data, dtype=np.uint8)
            if arr.size < w * h * 4:
                return False, None
            bgrx = np.ascontiguousarray(arr[: w * h * 4].reshape((h, w, 4)))
            return True, bgrx[:, :, :3].copy()
        finally:
            buf.unmap(mapinfo)

    def release(self) -> None:
        self._opened = False
        try:
            if getattr(self, "_pipe", None) is not None:
                self._pipe.set_state(self._Gst.State.NULL)
        except Exception:
            pass
        self._pipe = None
        self._sink = None

    def soft_restart(self) -> bool:
        """NULL → PLAYING on the same pipeline; rebuild if state change fails."""
        if not self._opened or self._pipe is None:
            return False
        Gst = self._Gst
        try:
            self._pipe.set_state(Gst.State.NULL)
            ret = self._pipe.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                self.release()
                return False
            # Keep soft restart short so capture lock / MJPEG stay responsive.
            deadline = time.perf_counter() + 1.5
            if ret == Gst.StateChangeReturn.ASYNC:
                state_ret, state, _pending = self._pipe.get_state(int(0.8 * Gst.SECOND))
                if state_ret == Gst.StateChangeReturn.FAILURE:
                    self.release()
                    return False
                if state not in (Gst.State.PLAYING, Gst.State.PAUSED):
                    self.release()
                    return False
            while time.perf_counter() < deadline:
                while self._ctx.pending():
                    self._ctx.iteration(False)
                msg = self._bus.timed_pop_filtered(50 * Gst.MSECOND, Gst.MessageType.ANY)
                if msg is not None and msg.type == Gst.MessageType.ERROR:
                    self.release()
                    return False
                sample = self._sink.emit("try-pull-sample", 100 * Gst.MSECOND)
                if sample is not None:
                    return True
            self.release()
            return False
        except Exception:
            try:
                self.release()
            except Exception:
                pass
            return False


def _libx264_record_args() -> list[str]:
    """Standard libx264 recording args (CPU)."""
    return [
        "-analyzeduration", "10M",
        "-probesize", "10M",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
    ]


def _gst_record_cmd(stream_url: str, output: str) -> list[str]:
    """GStreamer pipeline: NVDEC decode + L4T HW re-encode → MP4 (qtmux — official NVIDIA)."""
    enc = _gst_jetson_h264_encoder() or "nvv4l2h264enc"
    # GStreamer pipeline parser treats bare & as pad separator even inside
    # quoted rtspsrc location.  URL-encode & → %26 to keep the query string intact.
    safe_url = stream_url.replace("&", "%26")
    pipeline = (
        f'rtspsrc location="{safe_url}" latency=2000 protocols=tcp ! '
        "rtph264depay ! h264parse ! "
        "nvv4l2decoder enable-max-performance=1 num-extra-surfaces=4 ! "
        "nvvidconv ! video/x-raw(memory:NVMM),format=I420 ! "
        f"{enc} ! h264parse ! qtmux ! "
        f"filesink location={output}"
    )
    # gst-launch parses "!" only when argv is tokenized; a single pipeline string fails.
    return ["gst-launch-1.0", "-e", *shlex.split(pipeline)]


def _ffmpeg_record_cmd(
    *,
    stream_url: str,
    output: str,
    use_jetson_hw_encode: bool,
    record_stream_codec: str,
    encoding_mode: str = "cpu",
) -> list[str]:
    """Build FFmpeg recording command with robust timestamp/audio handling."""
    cmd = [
        "ffmpeg",
        "-y",
        "-fflags",
        "+genpts+igndts",
        "-use_wallclock_as_timestamps",
        "1",
        "-avoid_negative_ts",
        "make_zero",
        "-max_interleave_delta",
        "0",
        "-rtsp_transport",
        "tcp",
        "-i",
        stream_url,
        "-vsync",
        "2",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
    ]
    if (
        encoding_mode == "jetson"
        and use_jetson_hw_encode
        and (record_stream_codec or "h264").strip().lower() == "h264"
    ):
        if _ffmpeg_has_nvenc():  # defined below
            cmd += [
                "-hwaccel",
                "cuda",
                "-hwaccel_output_format",
                "cuda",
                "-c:v",
                "h264_nvenc",
                "-b:v",
                "2M",
                "-preset",
                "p4",
            ]
        else:
            cmd += _libx264_record_args()
    elif (record_stream_codec or "h264").strip().lower() == "h264":
        cmd += [
            "-analyzeduration",
            "10M",
            "-probesize",
            "10M",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
        ]
    else:
        cmd += [
            "-c:v",
            "copy",
        ]
    cmd += [
        "-af",
        "aresample=async=1:first_pts=0",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        output,
    ]
    return cmd


# Reconnect backoff: 1, 2, 4, 8, 16, max 30 sec
MAX_RECONNECT_DELAY = 30
INITIAL_RECONNECT_DELAY = 1
FFMPEG_CAPTURE_FAILURE_THRESHOLD = 3  # fdsink async=false даёт стабильные кадры
CLASSIFIER_RECORD_BUFFER_SIZE = 8
DEFAULT_CLASSIFIER_RECORD_MAX_SKEW_SEC = 0.35
# Avoid WARN spam when main/record RTSP is briefly unavailable (go2rtc busy / FFmpeg holds it).
RECORD_CAP_OPEN_COOLDOWN_SEC = 15.0
RECORD_CAP_FAIL_LOG_INTERVAL_SEC = 60.0


def _build_stream_url(
    go2rtc_url: str, stream_name: str, direct_url: str = None, username: str = None, password: str = None
) -> str:
    """Build RTSP URL for stream. Frigate/Go2RTC: HTTP API=1984, RTSP=8554."""
    if direct_url:
        return direct_url
    base = go2rtc_url.rstrip("/")
    if "://" in base:
        if base.startswith("http://"):
            base = "rtsp://" + base[7:]
        elif base.startswith("https://"):
            base = "rtsp://" + base[8:]
        # Go2RTC: HTTP on 1984, RTSP on 8554
        if ":1984" in base:
            base = base.replace(":1984", ":8554")
        # Optional auth: rtsp://user:pass@host:8554
        if username and password:
            # Insert user:pass@ after rtsp://
            base = base.replace("rtsp://", f"rtsp://{username}:{password}@", 1)
    return f"{base}/{stream_name}"


class Go2RTCStreamSource:
    """
    Video source from Go2RTC (RTSP/HLS).
    - capture() returns frames for motion/YOLO (or None on error/reconnect), optionally from a **detect** RTSP
    - start_recording/stop_recording uses FFmpeg on **stream_url** (main / record), Frigate-style
    - Auto-reconnect on stream failure
    - Optional MJPEG streaming server for live view (feeds from the same frames as capture())
    """

    def __init__(
        self,
        stream_url: str,
        main_size: tuple[int, int],
        lores_size: tuple[int, int] | None,
        auto_reconnect=True,
        pre_record_seconds=0,
        mjpeg_port=8082,
        encoding_mode="cpu",
        record_stream_codec="h264",
        capture_backend="auto",
        capture_stream_url: str | None = None,
        *,
        record_hw_encode: bool | None = None,
        single_rtsp_read: bool = False,
    ):
        self.logger = logging.getLogger(__name__)
        # Main/high stream: FFmpeg recording only.
        self.stream_url = stream_url
        # Detect substream (lores): motion, YOLO, ByteTrack — never fallback to main.
        capture_url = (capture_stream_url or "").strip()
        if not capture_url:
            raise ValueError(
                "Go2RTC detect substream URL required: set video.cameras[].detect_stream_name "
                "(main stream_url is record-only)"
            )
        if capture_url == (stream_url or "").strip():
            raise ValueError(
                "Go2RTC capture stream must differ from main record stream (detect_stream_name ≠ stream_name)"
            )
        self._capture_stream_url = capture_url
        self._single_rtsp_read = bool(single_rtsp_read)
        self.main_size = main_size
        self.lores_size = lores_size  # None = native RTSP resolution for detect/YOLO
        self._detect_native = lores_size is None
        self.auto_reconnect = auto_reconnect
        from encoding_utils import normalize_video_encoding

        self._encoding_mode = normalize_video_encoding(encoding_mode, "jetson")
        rsc = (record_stream_codec or "h264").strip().lower()
        self._record_stream_codec = rsc if rsc in ("h264", "copy") else "h264"
        self._capture_backend = _normalize_capture_backend(capture_backend)
        self._capture_backend_used = "opencv"
        _set_runtime_gauge("video_capture_backend_config", self._capture_backend)
        _set_runtime_gauge("video_capture_backend_fallback_reason", "not_set")

        self._cap = None
        self._out = None
        self._capture_process = None
        self._ffmpeg_process = None
        self._streaming_output = None
        self._streaming_thread = None
        self._recording = False
        self._recording_t0: float | None = None
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self._last_frame_time = 0
        self._frame_count = 0
        self._source_fps = 0.0
        self.stream_capabilities = None
        self._read_lock = threading.Lock()
        # API compat name: on jetson, True → NVENC/v4l2m2m/OMX; False → libx264.
        if record_hw_encode is None:
            self._record_hw_encode = True
        elif isinstance(record_hw_encode, bool):
            self._record_hw_encode = record_hw_encode
        else:
            from encoding_utils import parse_bool_config_flag

            self._record_hw_encode = parse_bool_config_flag(record_hw_encode, default=True)
        self._ffmpeg_capture_failures = 0
        self._force_opencv_until_ts = 0.0
        self._nvdec_opencv_cooldown_sec = 120.0
        self._soft_restart_failures_threshold = 3
        self._reconnect_debounce_sec = 3.0
        self._consecutive_read_failures = 0
        self._soft_restart_success_streak = 0
        self._soft_restart_max_success_streak = 2
        self._last_reconnect_attempt_ts = 0.0
        try:
            from app_config.app_config import app_config as _cfg

            self._nvdec_opencv_cooldown_sec = max(
                5.0, float(_cfg.get("video.capture_nvdec_opencv_cooldown_sec") or 120)
            )
            self._soft_restart_failures_threshold = max(
                1, int(_cfg.get("video.capture_soft_restart_failures") or 3)
            )
            self._reconnect_debounce_sec = max(
                0.5, float(_cfg.get("video.capture_reconnect_debounce_sec") or 3)
            )
            self._soft_restart_max_success_streak = max(
                1, int(_cfg.get("video.capture_soft_restart_max_success_streak") or 2)
            )
        except Exception:
            pass
        self._last_classifier_source_frame = None
        self._record_cap = None
        self._record_cap_fail_until_ts = 0.0
        self._record_cap_fail_log_ts = 0.0
        self._record_cap_fail_suppressed = 0
        self.record_stream_capabilities = None
        self._dual_stream = self._capture_stream_url != self.stream_url
        self._record_frame_buffer: deque[tuple[float, np.ndarray]] = deque(
            maxlen=CLASSIFIER_RECORD_BUFFER_SIZE,
        )
        self._last_detect_capture_ts: float | None = None
        self._last_classifier_crop_skew_sec: float = 0.0
        self._last_classifier_crop_mismatch: bool = False

        if self._single_rtsp_read:
            self.logger.info(
                "Go2RTC single RTSP read: main/record stream once per cycle; "
                "software lores for motion/YOLO/MJPEG (detect_stream_name kept for geometry config)."
            )
        elif self._dual_stream:
            self.logger.info(
                "Go2RTC dual-stream: capture (motion/YOLO/MJPEG) ≠ record (main RTSP). "
                "YOLO uses inference_lores_wh / letterbox only when decode size differs."
            )

        self._capture_url_connected: str | None = None
        self._connect()
        self._capture_url_connected = self._live_capture_url()
        self.refresh_record_stream_geometry()

        # Start MJPEG streaming server for live view
        self._streaming_output, self._streaming_thread = start_streaming_server(port=mjpeg_port)

    def _single_read_idle(self) -> bool:
        """Single main-stream read only when FFmpeg is not also pulling record RTSP."""
        return bool(self._single_rtsp_read and not self._recording)

    def _live_capture_url(self) -> str:
        """RTSP URL for live frame reads (main when single-read idle, else detect substream)."""
        if self._single_read_idle():
            return self.stream_url
        return self._capture_stream_url

    def _reconnect_capture_if_url_changed(self) -> None:
        """Reconnect capture when idle↔recording toggles capture URL."""
        with self._read_lock:
            expected = self._live_capture_url()
            current = getattr(self, "_capture_url_connected", None)
            if current == expected:
                return
            self.logger.info(
                "Capture URL switch: %s → %s (recording=%s single_rtsp_read=%s)",
                current or "?",
                expected,
                self._recording,
                self._single_rtsp_read,
            )
            if self._connect():
                self._capture_url_connected = expected
                self.refresh_record_stream_geometry()

    def _derive_detect_frame(self, main_frame: np.ndarray) -> np.ndarray:
        """Software lores from main frame (Frigate-style single read)."""
        if main_frame is None:
            return main_frame
        if self._detect_native or not self.lores_size:
            return np.ascontiguousarray(main_frame)
        from frame_geometry import frame_matches_target_wh, letterbox_bgr_to_wh

        out_wh = (int(self.lores_size[0]), int(self.lores_size[1]))
        if frame_matches_target_wh(main_frame, out_wh):
            return np.ascontiguousarray(main_frame)
        return letterbox_bgr_to_wh(main_frame, out_wh)

    def _arm_nvdec_opencv_cooldown(self, reason: str) -> None:
        global _NVDEC_OPENCV_COOLDOWN_UNTIL_MONO
        until = time.monotonic() + float(self._nvdec_opencv_cooldown_sec)
        self._force_opencv_until_ts = until
        _NVDEC_OPENCV_COOLDOWN_UNTIL_MONO = max(float(_NVDEC_OPENCV_COOLDOWN_UNTIL_MONO or 0.0), until)
        _inc_runtime_counter("video_capture_nvdec_fail_total", 1)
        _set_runtime_gauge("video_capture_backend_fallback_reason", reason)
        self.logger.warning(
            "GST NVDEC → sticky OpenCV for %.0fs (%s)",
            self._nvdec_opencv_cooldown_sec,
            reason,
        )

    def _connect(self) -> bool:
        """Open RTSP capture: Jetson NVDEC (GStreamer) when available, else OpenCV."""
        self._disconnect()
        now = time.monotonic()
        # Instance + process-wide cooldown (multi-camera / source rebuild).
        cooldown_until = max(
            float(self._force_opencv_until_ts or 0.0),
            float(_NVDEC_OPENCV_COOLDOWN_UNTIL_MONO or 0.0),
        )
        self._force_opencv_until_ts = cooldown_until
        in_cooldown = now < cooldown_until
        want_nvdec = (
            not in_cooldown
            and self._capture_backend in ("auto", "ffmpeg_nvmpi")
            and self._encoding_mode == "jetson"
            and _gst_nvdec_capture_available()
        )
        if want_nvdec:
            self.logger.info("Connecting to video stream (GStreamer nvv4l2decoder NVDEC, capture/detect)")
            try:
                cap = _GstRtspNvdecCapture(self._live_capture_url())
            except Exception as exc:
                self.logger.warning("GST NVDEC capture open failed: %s", exc)
                cap = None
            if cap is not None and cap.isOpened():
                self._cap = cap
                self._apply_stream_probe()
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps and fps > 0 and (self._source_fps or 0) <= 0.5:
                    self._source_fps = float(fps)
                self._capture_backend_used = "ffmpeg_nvmpi"
                # Do not reset consecutive here: open-ok/read-stall must still
                # accumulate toward soft-restart / sticky OpenCV.
                _set_runtime_gauge("video_capture_backend_used", self._capture_backend_used)
                _set_runtime_gauge("video_capture_backend_fallback_reason", "nvdec_ok")
                self._reconnect_delay = INITIAL_RECONNECT_DELAY
                self.logger.info("Connected (NVDEC). FPS: %s", self._source_fps)
                return True
            self._arm_nvdec_opencv_cooldown("nvdec_open_fail")
        elif in_cooldown:
            _set_runtime_gauge("video_capture_backend_fallback_reason", "nvdec_cooldown")

        self.logger.info("Connecting to video stream (OpenCV, capture/detect)")
        cap = cv2.VideoCapture(self._live_capture_url(), cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self.logger.error("Failed to open stream")
            return False
        self._cap = cap
        self._apply_stream_probe()
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0 and (self._source_fps or 0) <= 0.5:
            self._source_fps = float(fps)
        self._capture_backend_used = "opencv"
        # OpenCV path: clear NVDEC soft-restart bookkeeping only.
        self._soft_restart_success_streak = 0
        _set_runtime_gauge("video_capture_backend_used", self._capture_backend_used)
        if want_nvdec or in_cooldown:
            _set_runtime_gauge(
                "video_capture_backend_fallback_reason",
                "nvdec_cooldown" if in_cooldown else "fallback_to_opencv",
            )
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self.logger.info("Connected. FPS: %s", self._source_fps)
        return True

    def _apply_stream_probe(self) -> None:
        """Probe detect/capture stream and attach StreamCapabilities."""
        try:
            from stream_probe import attach_stream_capabilities, probe_stream_url, publish_probe_gauges

            caps = probe_stream_url(self._live_capture_url())
            if caps is not None:
                attach_stream_capabilities(self, caps)
                if caps.fps > 0.5:
                    self._source_fps = float(caps.fps)
                publish_probe_gauges(caps)
                self.logger.info(
                    "Detect stream probe: %sx%s @ %.2f fps (%s)",
                    caps.width,
                    caps.height,
                    caps.fps or self._source_fps,
                    caps.source,
                )
        except Exception as exc:
            from processor_exception_handling import reraise_if_critical

            reraise_if_critical(exc)
            self.logger.debug("stream probe skipped: %s", exc)

    def refresh_record_stream_geometry(self) -> tuple[int, int] | None:
        """Probe main/record RTSP and refresh ``main_size`` for bbox remap + playback."""
        if not self._dual_stream:
            return self.main_size
        try:
            from app_config.app_config import app_config
            from stream_probe import force_recording_resolution, probe_stream_url, publish_probe_gauges

            if force_recording_resolution(app_config):
                return self.main_size

            caps = probe_stream_url(self.stream_url)
        except Exception as exc:
            from processor_exception_handling import reraise_if_critical

            reraise_if_critical(exc)
            self.logger.debug("record stream probe skipped: %s", exc)
            return self.main_size
        if caps is None or caps.width <= 0 or caps.height <= 0:
            return self.main_size
        self.record_stream_capabilities = caps
        probed = (int(caps.width), int(caps.height))
        prev = tuple(self.main_size) if self.main_size and len(self.main_size) >= 2 else None
        if prev != probed:
            if prev is not None:
                _inc_runtime_counter("bbox_remap_mismatch_total")
                self.logger.warning(
                    "record stream geometry: config/main_size=%sx%s probed=%sx%s source=%s",
                    prev[0],
                    prev[1],
                    probed[0],
                    probed[1],
                    caps.source,
                )
            else:
                self.logger.info(
                    "record stream probe: %sx%s @ %.2f fps (%s)",
                    caps.width,
                    caps.height,
                    caps.fps or 0.0,
                    caps.source,
                )
        self.main_size = probed
        try:
            publish_probe_gauges(caps)
            _set_runtime_gauge("record_stream_probe_width", int(caps.width))
            _set_runtime_gauge("record_stream_probe_height", int(caps.height))
        except Exception:
            self.logger.debug("record stream probe gauges failed", exc_info=True)
        return self.main_size

    def _disconnect_record_cap(self) -> None:
        if self._record_cap is not None:
            try:
                self._record_cap.release()
            except Exception:
                self.logger.debug("record cap release failed", exc_info=True)
            self._record_cap = None

    def _connect_record_cap(self) -> bool:
        """Open main/record RTSP for hi-res classifier crops (dual-read idle only).

        While FFmpeg records, main RTSP is already open — skip second VideoCapture.
        Classifier crops use the ring buffer seeded before/during idle single-read.
        """
        if not self._dual_stream:
            return False
        if self._single_rtsp_read and not self._recording:
            return False
        if self._recording:
            return False
        now = time.monotonic()
        if now < float(self._record_cap_fail_until_ts or 0.0):
            return False
        self._disconnect_record_cap()
        cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self._record_cap_fail_until_ts = now + RECORD_CAP_OPEN_COOLDOWN_SEC
            suppressed = int(self._record_cap_fail_suppressed or 0)
            if now - float(self._record_cap_fail_log_ts or 0.0) >= RECORD_CAP_FAIL_LOG_INTERVAL_SEC:
                if suppressed:
                    self.logger.warning(
                        "Failed to open record stream for classifier crops "
                        "(suppressed %s similar in last %.0fs; cooldown %.0fs)",
                        suppressed,
                        RECORD_CAP_FAIL_LOG_INTERVAL_SEC,
                        RECORD_CAP_OPEN_COOLDOWN_SEC,
                    )
                else:
                    self.logger.warning("Failed to open record stream for classifier crops")
                self._record_cap_fail_log_ts = now
                self._record_cap_fail_suppressed = 0
            else:
                self._record_cap_fail_suppressed = suppressed + 1
            _inc_runtime_counter("record_stream_open_fail_total", 1)
            try:
                cap.release()
            except Exception:
                pass
            return False
        self._record_cap_fail_until_ts = 0.0
        self._record_cap = cap
        return True

    def _classifier_record_max_skew_sec(self) -> float:
        try:
            from app_config.app_config import app_config

            raw = app_config.get("processor.classifier_record_max_skew_sec")
            if raw is not None:
                v = float(raw)
                if v > 0:
                    return v
        except (TypeError, ValueError):
            pass
        return DEFAULT_CLASSIFIER_RECORD_MAX_SKEW_SEC

    def _select_nearest_record_frame(self, detect_ts: float) -> tuple[np.ndarray | None, float]:
        if not self._record_frame_buffer:
            return None, 0.0
        best_ts, best_frame = min(
            self._record_frame_buffer,
            key=lambda item: abs(item[0] - detect_ts),
        )
        return best_frame, abs(best_ts - detect_ts)

    def get_last_detect_capture_ts(self) -> float | None:
        return self._last_detect_capture_ts

    def get_classifier_crop_skew_sec(self) -> float:
        return float(self._last_classifier_crop_skew_sec)

    def classifier_crop_source_mismatch(self) -> bool:
        return bool(self._last_classifier_crop_mismatch)

    def _read_record_classifier_frame(self) -> np.ndarray | None:
        """Best-effort hi-res frame from main/record RTSP (dual-read / recording fallback)."""
        if not self._dual_stream:
            return None
        if self._single_rtsp_read and not self._recording:
            return None
        with self._read_lock:
            cap = self._record_cap
            if cap is None or not cap.isOpened():
                if not self._connect_record_cap():
                    return None
                cap = self._record_cap
            if cap is None:
                return None
            ret, frame = cap.read()
            if not ret or frame is None:
                self._disconnect_record_cap()
                return None
            return frame

    def _disconnect(self):
        """Close RTSP connection."""
        self._disconnect_record_cap()
        if self._cap:
            self._cap.release()
            self._cap = None
        self._capture_backend_used = "opencv"

    def _soft_restart_capture(self) -> bool:
        """NVDEC soft restart on same URL without backoff sleep."""
        if self._capture_backend_used != "ffmpeg_nvmpi":
            return False
        cap = self._cap
        if not isinstance(cap, _GstRtspNvdecCapture):
            return False
        ok = bool(cap.soft_restart())
        _inc_runtime_counter("video_capture_soft_restart_total", 1)
        if ok:
            self._consecutive_read_failures = 0
            self._soft_restart_success_streak = int(self._soft_restart_success_streak or 0) + 1
            self.logger.info(
                "NVDEC soft restart ok (streak=%s)",
                self._soft_restart_success_streak,
            )
            return True
        self.logger.warning("NVDEC soft restart failed")
        self._soft_restart_success_streak = 0
        return False

    def _reconnect_if_needed(self) -> bool:
        """Attempt reconnect with backoff. Returns True if connected."""
        if not self.auto_reconnect:
            return False
        now = time.monotonic()
        same_url = self._live_capture_url() == getattr(self, "_capture_url_connected", None)
        if same_url and (now - float(self._last_reconnect_attempt_ts or 0.0)) < float(
            self._reconnect_debounce_sec
        ):
            _inc_runtime_counter("video_capture_reconnect_debounced_total", 1)
            return False
        while True:
            # Ожидаемое поведение при кратковременных обрывах RTSP; не WARNING — иначе шум в логах/алертах.
            self.logger.info("Reconnecting in %ss...", self._reconnect_delay)
            _inc_runtime_counter("video_capture_reconnect_total", 1)
            time.sleep(self._reconnect_delay)
            ok = self._connect()
            # Debounce from connect completion (NVDEC open can take several seconds).
            self._last_reconnect_attempt_ts = time.monotonic()
            if ok:
                self._capture_url_connected = self._live_capture_url()
                self.refresh_record_stream_geometry()
                return True
            self._reconnect_delay = min(self._reconnect_delay * 2, MAX_RECONNECT_DELAY)

    def _read_frame(self, *, track_health: bool = True):
        """Read one frame. Returns (frame_bgr, success).

        ``track_health=False`` for MJPEG feeder so it does not mutate soft-restart
        / consecutive counters used by ``capture()``.
        """
        if not self._cap or not self._cap.isOpened():
            if track_health:
                self._consecutive_read_failures += 1
            return None, False
        ret, frame = self._cap.read()
        if not ret or frame is None:
            if track_health:
                self._consecutive_read_failures += 1
            return None, False
        if track_health:
            self._consecutive_read_failures = 0
            # Stable frame means soft-restart loop is broken; allow soft again later.
            self._soft_restart_success_streak = 0
        return frame, True

    def _update_streaming_output(self, frame):
        """Push frame to MJPEG streaming server."""
        if self._streaming_output and frame is not None:
            _, jpeg = cv2.imencode(".jpg", frame)
            if jpeg is not None:
                self._streaming_output.write(jpeg.tobytes())
    def start_recording(self, output: str):
        """Start recording: GStreamer on Jetson, FFmpeg otherwise."""
        self._recording = True
        self._reconnect_capture_if_url_changed()
        self._recording_t0 = time.monotonic()
        self._video_output = output
        os.makedirs(os.path.dirname(output), exist_ok=True)
        use_jetson = self._encoding_mode == "jetson"
        use_jetson_hw = use_jetson and self._record_hw_encode
        if (
            use_jetson_hw
            and self._record_stream_codec == "h264"
            and _gst_jetson_record_available()
        ):
            cmd = _gst_record_cmd(self.stream_url, output)
            enc = _gst_jetson_h264_encoder() or "nvv4l2h264enc"
            backend_label = f"GStreamer {enc} (Jetson HW)"
        else:
            cmd = _ffmpeg_record_cmd(
                stream_url=self.stream_url,
                output=output,
                use_jetson_hw_encode=bool(use_jetson_hw),
                record_stream_codec=self._record_stream_codec,
                encoding_mode=self._encoding_mode,
            )
            if use_jetson_hw and self._record_stream_codec == "h264" and _ffmpeg_has_nvenc():
                backend_label = "FFmpeg NVENC (CUDA)"
            elif use_jetson_hw and self._record_stream_codec == "h264":
                backend_label = "Jetson HW"
            else:
                backend_label = "CPU (libx264)"
        try:
            from encoding_status import set_last_encoding_used

            if use_jetson_hw and self._record_stream_codec == "h264" and _gst_jetson_record_available():
                enc = _gst_jetson_h264_encoder() or ""
                set_last_encoding_used("v4l2m2m" if enc == "nvv4l2h264enc" else "omx")
            elif use_jetson_hw and self._record_stream_codec == "h264" and _ffmpeg_has_nvenc():
                set_last_encoding_used("nvenc")
            elif self._record_stream_codec == "h264":
                set_last_encoding_used("x264_cpu")
            else:
                set_last_encoding_used("cpu")
        except Exception:
            self.logger.debug("encoding_status recording path failed", exc_info=True)
        self.logger.info(
            "Starting recording to %s (%s)",
            output,
            backend_label,
        )
        self._ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._frame_count = 0
        self._last_frame_time = None

    def stop_recording(self):
        """Stop FFmpeg recording."""
        self._recording = False
        self._disconnect_record_cap()
        self._reconnect_capture_if_url_changed()
        self._recording_t0 = None
        if self._ffmpeg_process:
            return_code = None
            stderr_text = ""
            try:
                # gst-launch -e finalizes qtmux/mp4 on SIGINT; SIGTERM drops the file.
                proc_args = self._ffmpeg_process.args
                uses_gst = (
                    isinstance(proc_args, (list, tuple))
                    and proc_args
                    and os.path.basename(str(proc_args[0])) == "gst-launch-1.0"
                )
                if uses_gst:
                    self._ffmpeg_process.send_signal(signal.SIGINT)
                else:
                    self._ffmpeg_process.terminate()
                return_code = self._ffmpeg_process.wait(timeout=10 if uses_gst else 5)
            except subprocess.TimeoutExpired:
                self._ffmpeg_process.kill()
                return_code = self._ffmpeg_process.wait(timeout=2)
            except Exception as e:
                self.logger.warning("Error stopping FFmpeg: %s", e)
            if self._ffmpeg_process and self._ffmpeg_process.stderr:
                try:
                    err = self._ffmpeg_process.stderr.read()
                    if err:
                        stderr_text = err.decode("utf-8", errors="replace")
                        for line in stderr_text.strip().splitlines():
                            safe = _sanitize_ffmpeg_stderr_line(line)
                            lvl = _ffmpeg_stderr_log_level(safe)
                            self.logger.log(lvl, "FFmpeg: %s", safe)
                except Exception:
                    self.logger.debug("FFmpeg stderr drain failed", exc_info=True)
            self._ffmpeg_process = None
        self.logger.info("Recording stopped")

    def capture(self):
        """
        Get next frame for processing (native BGR from stream).

        Letterbox/resize for YOLO runs in ``detection_strategy`` via ``prepare_yolo_detector_frame``.
        """
        # One reconnect attempt per capture call: avoid recursive stack growth
        # and keep motion loop responsive when stream stays unavailable.
        for attempt in range(2):
            with self._read_lock:
                frame, ok = self._read_frame()
            if ok and frame is not None:
                break
            if attempt == 0:
                # Soft restart NVDEC before full reconnect/backoff.
                if (
                    self._consecutive_read_failures >= int(self._soft_restart_failures_threshold)
                    and self._capture_backend_used == "ffmpeg_nvmpi"
                    and self._live_capture_url() == getattr(self, "_capture_url_connected", None)
                ):
                    streak = int(getattr(self, "_soft_restart_success_streak", 0) or 0)
                    max_streak = int(getattr(self, "_soft_restart_max_success_streak", 2) or 2)
                    if streak >= max_streak:
                        # Soft keeps "succeeding" but reads still fail → sticky OpenCV.
                        self._arm_nvdec_opencv_cooldown("nvdec_soft_restart_loop")
                        self._last_reconnect_attempt_ts = 0.0
                    else:
                        with self._read_lock:
                            soft_ok = self._soft_restart_capture()
                        if soft_ok:
                            continue
                        # Soft restart exhausted → sticky OpenCV cooldown then reconnect.
                        self._arm_nvdec_opencv_cooldown("nvdec_read_stall")
                        # Bypass debounce so we leave broken NVDEC immediately.
                        self._last_reconnect_attempt_ts = 0.0
                if self._reconnect_if_needed():
                    continue
            return None
        self._frame_count += 1
        self._last_frame_time = time.time()
        detect_ts = time.monotonic()
        self._last_detect_capture_ts = detect_ts
        if self._single_read_idle():
            main_frame = frame
            self._last_classifier_crop_skew_sec = 0.0
            self._last_classifier_crop_mismatch = False
            self._last_classifier_source_frame = main_frame
            self._record_frame_buffer.append((detect_ts, main_frame))
            frame = self._derive_detect_frame(main_frame)
        elif self._dual_stream:
            record_frame = self._read_record_classifier_frame()
            if record_frame is not None:
                self._record_frame_buffer.append((detect_ts, record_frame))
            selected, skew = self._select_nearest_record_frame(detect_ts)
            self._last_classifier_crop_skew_sec = skew
            max_skew = self._classifier_record_max_skew_sec()
            mismatch = selected is None or skew > max_skew
            self._last_classifier_crop_mismatch = mismatch
            self._last_classifier_source_frame = None if mismatch else selected
        else:
            self._last_classifier_crop_skew_sec = 0.0
            self._last_classifier_crop_mismatch = False
            self._last_classifier_source_frame = frame
        self._update_streaming_output(frame)
        return frame

    def get_classifier_source_frame(self, detect_ts: float | None = None):
        """Best-effort hi-res (record) or detect frame for classifier/ReID crops."""
        if self._last_classifier_crop_mismatch:
            return None
        ts = detect_ts if detect_ts is not None else self._last_detect_capture_ts
        if (not self._single_read_idle()) and self._dual_stream and ts is not None:
            selected, skew = self._select_nearest_record_frame(ts)
            if selected is not None and skew <= self._classifier_record_max_skew_sec():
                return selected
            return None
        return self._last_classifier_source_frame

    def get_frame_time(self):
        """Seconds on main MP4 timeline (monotonic elapsed since FFmpeg record start)."""
        if self._recording and self._recording_t0 is not None:
            return round(time.monotonic() - self._recording_t0, 2)
        return None

    def push_one_frame_to_mjpeg(self):
        """Read one frame and push to MJPEG (for live view). Skips if main thread is reading."""
        if not self._streaming_output:
            return
        if not self._read_lock.acquire(blocking=False):
            return
        try:
            frame, ok = self._read_frame(track_health=False)
            if ok and frame is not None:
                if self._single_read_idle():
                    frame = self._derive_detect_frame(frame)
                self._update_streaming_output(frame)
        finally:
            self._read_lock.release()

    def close(self):
        """Release resources."""
        self.stop_recording()
        self._disconnect()
        if self._streaming_output:
            self._streaming_output.close()
