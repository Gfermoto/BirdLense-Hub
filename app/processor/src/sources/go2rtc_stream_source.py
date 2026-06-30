"""
Go2RTC stream source for x86/Docker deployment.
Reads video from RTSP/HLS URL (Go2RTC), supports auto-reconnect, recording via FFmpeg.
Encoding: cpu (copy), intel (VA-API), or jetson (GStreamer NVMPI on Jetson NVDEC).
"""

import glob
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque

import cv2
import numpy as np


from .streaming_server import start_streaming_server

logger = logging.getLogger(__name__)

VAAPI_DEVICE = "/dev/dri/renderD128"

NVMPI_GST_TEMPLATE = (
    "rtspsrc location={url} latency=300 drop-on-latency=true protocols=4 ! "
    "rtph264depay ! h264parse ! "
    "nvv4l2decoder enable-max-performance=1 num-extra-surfaces=12 ! "
    "nvvidconv ! video/x-raw(memory:NVMM),format=I420 ! "
    "nvvidconv ! video/x-raw,format=I420,width={w},height={h} ! "
    "fdsink fd=1"
)


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


def _normalize_capture_backend(value: str | None) -> str:
    """Normalize live frame capture backend."""
    backend = (value or "auto").strip().lower()
    if backend in ("auto", "opencv", "ffmpeg_vaapi", "ffmpeg_nvmpi"):
        return backend
    return "auto"


def _capture_fallback_reason(
    *,
    requested_backend: str,
    encoding_mode: str,
    vaapi_available: bool,
    nvmpi_available: bool = False,
) -> str:
    """Classify fallback reason for capture backend telemetry."""
    rb = _normalize_capture_backend(requested_backend)
    enc = (encoding_mode or "cpu").strip().lower()
    if rb == "opencv":
        return "requested_opencv"
    if rb == "ffmpeg_vaapi" and not vaapi_available:
        return "vaapi_unavailable"
    if rb == "ffmpeg_nvmpi" and not nvmpi_available:
        return "nvmpi_unavailable"
    if rb == "auto" and enc == "jetson" and not nvmpi_available:
        return "auto_nvmpi_probe_failed"
    if rb == "auto" and enc != "intel":
        return "auto_prefers_opencv_for_non_intel_encoding"
    if rb == "auto" and not vaapi_available:
        return "auto_vaapi_probe_failed"
    return "fallback_to_opencv"


def _ffmpeg_vaapi_capture_cmd(stream_url: str, lores_size: tuple[int, int]) -> list[str]:
    """FFmpeg rawvideo command for VA-API live inference capture."""
    width, height = int(lores_size[0]), int(lores_size[1])
    # Preserve source aspect ratio and pad to inference canvas (letterbox),
    # matching OpenCV capture path semantics.
    vf = (
        f"scale_vaapi=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"hwdownload,format=nv12,pad=w={width}:h={height}:x=(ow-iw)/2:y=(oh-ih)/2,"
        "format=bgr24"
    )
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-fflags",
        "+genpts",
        "-use_wallclock_as_timestamps",
        "1",
        "-rtsp_transport",
        "tcp",
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        VAAPI_DEVICE,
        "-hwaccel_output_format",
        "vaapi",
        "-i",
        stream_url,
        "-an",
        "-vf",
        vf,
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]


def _gst_nvmpi_capture_cmd(stream_url: str, lores_size: tuple[int, int]) -> list[str]:
    """GStreamer NVMM pipeline for Jetson NVDEC live inference capture."""
    width, height = int(lores_size[0]), int(lores_size[1])
    pipeline = NVMPI_GST_TEMPLATE.format(url=stream_url, w=width, h=height)
    return ["gst-launch-1.0", "-e", pipeline]


def _jetson_v4l2enc_available() -> bool:
    """Check if V4L2 devices exist AND ffmpeg has h264_v4l2m2m encoder."""
    if not glob.glob("/dev/video*"):
        return False
    try:
        out = subprocess.run(
            ["ffmpeg", "-encoders"], capture_output=True, timeout=5,
        ).stdout.decode()
        return "h264_v4l2m2m" in out
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _ffmpeg_has_omx() -> bool:
    """Check if ffmpeg has h264_omx encoder (OpenMAX IL on Jetson)."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-encoders"], capture_output=True, timeout=5,
        ).stdout.decode()
        return "h264_omx" in out
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _ffmpeg_has_nvenc() -> bool:
    """Check if ffmpeg has h264_nvenc (NVIDIA NVENC, Orin Docker / desktop)."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-encoders"], capture_output=True, timeout=5,
        ).stdout.decode()
        return "h264_nvenc" in out
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _gst_jetson_record_available() -> bool:
    """GStreamer NVMM record path (L4T native Jetson, not generic CUDA Docker)."""
    try:
        out = subprocess.run(
            ["gst-inspect-1.0", "nvv4l2decoder"],
            capture_output=True,
            timeout=5,
        )
        if out.returncode != 0:
            return False
        out2 = subprocess.run(
            ["gst-inspect-1.0", "omxh264enc"],
            capture_output=True,
            timeout=5,
        )
        return out2.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
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
    """GStreamer pipeline: NVDEC decode + OMX re-encode → MP4."""
    pipeline = (
        f"rtspsrc location={stream_url} latency=300 ! "
        "rtph264depay ! h264parse ! "
        "nvv4l2decoder enable-max-performance=1 num-extra-surfaces=2 ! "
        "nvvidconv ! video/x-raw(memory:NVMM),format=I420 ! "
        "omxh264enc ! h264parse ! mp4mux ! "
        f"filesink location={output}"
    )
    return ["gst-launch-1.0", "-e", pipeline]


def _ffmpeg_record_cmd(
    *,
    stream_url: str,
    output: str,
    use_vaapi: bool,
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
    ]
    if use_vaapi:
        # More stable than mixed hw decode+encode on some iGPU/driver combos:
        # decode in software and upload NV12 frames for VA-API encoder explicitly.
        cmd += [
            "-vaapi_device",
            VAAPI_DEVICE,
        ]
    cmd += [
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
    if use_vaapi:
        cmd += [
            "-vf",
            "format=nv12,hwupload",
            "-c:v",
            "h264_vaapi",
            "-b:v",
            "2M",
        ]
    elif encoding_mode == "jetson" and (record_stream_codec or "h264").strip().lower() == "h264":
        if _jetson_v4l2enc_available():
            cmd += [
                "-c:v",
                "h264_v4l2m2m",
                "-b:v",
                "2M",
            ]
        elif _ffmpeg_has_omx():
            cmd += [
                "-c:v",
                "h264_omx",
                "-b:v",
                "2M",
            ]
        elif _ffmpeg_has_nvenc():
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
FFMPEG_CAPTURE_FAILURE_THRESHOLD = 3
FFMPEG_CAPTURE_COOLDOWN_SEC = 60
CLASSIFIER_RECORD_BUFFER_SIZE = 8
DEFAULT_CLASSIFIER_RECORD_MAX_SKEW_SEC = 0.35


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
        record_with_vaapi: bool | None = None,
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
        self._encoding_mode = (encoding_mode or "jetson").strip().lower()
        if self._encoding_mode in ("orin", "nvenc"):
            self._encoding_mode = "jetson"
        if self._encoding_mode not in ("cpu", "intel", "jetson"):
            self._encoding_mode = "jetson"
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
        self._vaapi_checked = False
        self._vaapi_available = True
        self._vaapi_record_available = True
        self._nvmpi_checked: bool = False
        self._nvmpi_available: bool = False
        self._nvmpi_fallback_permanent: bool = False
        # When encoding=intel: still use VA-API for ffmpeg capture (auto) unless capture falls back;
        # recording can use libx264 only if record_with_vaapi is false (avoids flaky h264_vaapi on some iGPU drivers).
        if record_with_vaapi is None:
            self._record_with_vaapi = True
        elif isinstance(record_with_vaapi, bool):
            self._record_with_vaapi = record_with_vaapi
        else:
            s = str(record_with_vaapi).strip().lower()
            self._record_with_vaapi = s not in ("0", "false", "no", "off")
        self._recording_used_vaapi = False
        self._ffmpeg_capture_failures = 0
        self._force_opencv_until_ts = 0.0
        self._last_classifier_source_frame = None
        self._record_cap = None
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
        """Reconnect OpenCV/VA-API capture when idle↔recording toggles capture URL."""
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

    def _connect(self) -> bool:
        """Open RTSP connection. Returns True if successful."""
        self._disconnect()
        if self._should_use_ffmpeg_vaapi_capture() and self._connect_ffmpeg_vaapi_capture():
            return True
        if self._should_use_ffmpeg_vaapi_capture():
            reason = _capture_fallback_reason(
                requested_backend=self._capture_backend,
                encoding_mode=self._encoding_mode,
                vaapi_available=self._vaapi_available,
            )
            _set_runtime_gauge("video_capture_backend_fallback_reason", reason)
            _inc_runtime_counter("video_capture_backend_fallback_total", 1)
        if self._should_use_nvmpi_capture() and self._connect_ffmpeg_nvmpi_capture():
            return True
        # Не логировать поля из URL (в т.ч. учётка в stream_url) — CodeQL sensitive logging
        self.logger.info("Connecting to video stream (OpenCV, capture/detect)")
        # OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp set in Dockerfile
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
        _set_runtime_gauge("video_capture_backend_used", self._capture_backend_used)
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self.logger.info(f"Connected. FPS: {self._source_fps}")
        return True

    def _should_use_ffmpeg_vaapi_capture(self) -> bool:
        """Whether live inference capture should try FFmpeg VA-API."""
        if self._detect_native or not self.lores_size:
            return False
        if time.time() < float(self._force_opencv_until_ts or 0.0):
            return False
        if self._capture_backend == "ffmpeg_vaapi":
            return True
        return self._capture_backend == "auto" and self._encoding_mode == "intel"

    def _connect_ffmpeg_vaapi_capture(self) -> bool:
        """Open FFmpeg rawvideo pipe for live inference frames."""
        if not self._use_intel_vaapi():
            if self._capture_backend == "ffmpeg_vaapi":
                self.logger.warning("FFmpeg VA-API capture requested but VA-API is unavailable; falling back to OpenCV")
            return False
        cmd = _ffmpeg_vaapi_capture_cmd(self._live_capture_url(), self.lores_size)
        try:
            self._capture_process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError) as e:
            self.logger.warning("Failed to start FFmpeg VA-API capture: %s", e)
            self._capture_process = None
            return False
        self._capture_backend_used = "ffmpeg_vaapi"
        _set_runtime_gauge("video_capture_backend_used", self._capture_backend_used)
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self._apply_stream_probe()
        self.logger.info("Connected. Capture backend: FFmpeg VA-API")
        return True

    def _should_use_nvmpi_capture(self) -> bool:
        """Whether to try Jetson GStreamer NVMPI for inference frames."""
        if self._detect_native or not self.lores_size:
            return False
        if self._nvmpi_fallback_permanent:
            self.logger.debug("NVMPI: permanent fallback active, skip")
            return False
        if time.time() < float(self._force_opencv_until_ts or 0.0):
            return False
        if self._capture_backend == "ffmpeg_nvmpi":
            if not self._nvmpi_fallback_permanent:
                return True
            return False
        return self._capture_backend == "auto" and self._encoding_mode == "jetson"

    def _connect_ffmpeg_nvmpi_capture(self) -> bool:
        """Open GStreamer NVMM pipeline for live inference (Jetson NVDEC)."""
        if not self._use_jetson_nvmpi():
            if self._capture_backend == "ffmpeg_nvmpi":
                self.logger.warning("NVMPI requested but unavailable; fallback to OpenCV")
            return False
        cmd = _gst_nvmpi_capture_cmd(self._live_capture_url(), self.lores_size)
        try:
            self._capture_process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as e:
            self.logger.warning("Failed to start GStreamer NVMPI: %s", e)
            self._capture_process = None
            return False
        self._capture_backend_used = "ffmpeg_nvmpi"
        _set_runtime_gauge("video_capture_backend_used", self._capture_backend_used)
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self._apply_stream_probe()
        self.logger.info("Connected. Capture: GStreamer NVMPI (Jetson NVDEC)")
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
        self._disconnect_record_cap()
        cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self.logger.warning("Failed to open record stream for classifier crops")
            return False
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
        if self._capture_process:
            try:
                self._capture_process.terminate()
                self._capture_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._capture_process.kill()
                self._capture_process.wait(timeout=2)
            except Exception:
                logger.debug("ffmpeg capture process shutdown cleanup failed", exc_info=True)
            self._capture_process = None
        self._capture_backend_used = "opencv"

    def _reconnect_if_needed(self) -> bool:
        """Attempt reconnect with backoff. Returns True if connected."""
        if not self.auto_reconnect:
            return False
        while True:
            # Ожидаемое поведение при кратковременных обрывах RTSP; не WARNING — иначе шум в логах/алертах.
            self.logger.info("Reconnecting in %ss...", self._reconnect_delay)
            _inc_runtime_counter("video_capture_reconnect_total", 1)
            time.sleep(self._reconnect_delay)
            if self._connect():
                self.refresh_record_stream_geometry()
                return True
            self._reconnect_delay = min(self._reconnect_delay * 2, MAX_RECONNECT_DELAY)

    def _read_frame(self):
        """Read one frame. Returns (frame_bgr, success)."""
        if self._capture_backend_used == "ffmpeg_vaapi":
            return self._read_ffmpeg_vaapi_frame()
        if self._capture_backend_used == "ffmpeg_nvmpi":
            return self._read_gst_nvmpi_frame()
        if not self._cap or not self._cap.isOpened():
            return None, False
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None, False
        return frame, True

    def _read_ffmpeg_vaapi_frame(self):
        """Read one BGR lores frame from FFmpeg rawvideo stdout."""
        proc = self._capture_process
        if not proc or proc.poll() is not None or not proc.stdout:
            self._ffmpeg_capture_failures += 1
            return None, False
        width, height = int(self.lores_size[0]), int(self.lores_size[1])
        need = width * height * 3
        chunks = []
        remaining = need
        while remaining > 0:
            chunk = proc.stdout.read(remaining)
            if not chunk:
                self._ffmpeg_capture_failures += 1
                return None, False
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        self._ffmpeg_capture_failures = 0
        return frame, True

    def _read_gst_nvmpi_frame(self):
        """Read one I420 frame from GStreamer NVMM pipeline, convert to BGR."""
        proc = self._capture_process
        if not proc or proc.poll() is not None or not proc.stdout:
            self._ffmpeg_capture_failures += 1
            return None, False
        width, height = int(self.lores_size[0]), int(self.lores_size[1])
        i420_size = width * height * 3 // 2  # 1.5 bytes/pixel
        chunks = []
        remaining = i420_size
        while remaining > 0:
            chunk = proc.stdout.read(remaining)
            if not chunk:
                self._ffmpeg_capture_failures += 1
                self.logger.warning("GStreamer NVMPI pipe read returned empty")
                return None, False
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        i420 = np.frombuffer(data, dtype=np.uint8).reshape((height * 3 // 2, width))
        frame = cv2.cvtColor(i420, cv2.COLOR_YUV2BGR_I420)
        self._ffmpeg_capture_failures = 0
        return frame, True

    def _update_streaming_output(self, frame):
        """Push frame to MJPEG streaming server."""
        if self._streaming_output and frame is not None:
            _, jpeg = cv2.imencode(".jpg", frame)
            if jpeg is not None:
                self._streaming_output.write(jpeg.tobytes())

    def _probe_vaapi(self) -> bool:
        """Check if VA-API encode path works in this container."""
        probe_out = "/tmp/birdlense_vaapi_probe.mp4"
        try:
            r = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-vaapi_device",
                    VAAPI_DEVICE,
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=640x360:rate=5:duration=1",
                    "-vf",
                    "format=nv12,hwupload",
                    "-c:v",
                    "h264_vaapi",
                    "-frames:v",
                    "5",
                    "-an",
                    probe_out,
                ],
                capture_output=True,
                timeout=10,
            )
            if r.returncode != 0 and r.stderr:
                self.logger.debug("VA-API probe stderr: %s", r.stderr.decode("utf-8", errors="replace")[:300])
            ok = r.returncode == 0 and os.path.exists(probe_out) and os.path.getsize(probe_out) > 1024
            try:
                if os.path.exists(probe_out):
                    os.remove(probe_out)
            except OSError:
                pass
            return ok
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.logger.debug("VA-API probe failed: %s", e)
            return False

    def _probe_nvmpi(self) -> bool:
        """Check if Jetson hardware decoder is available (gst-inspect-1.0 nvv4l2decoder)."""
        if not shutil.which("gst-inspect-1.0"):
            self.logger.debug("NVMPI probe: gst-inspect-1.0 not found")
            return False
        try:
            r = subprocess.run(
                ["gst-inspect-1.0", "nvv4l2decoder"],
                capture_output=True, timeout=10,
            )
            ok = r.returncode == 0
            if not ok:
                self.logger.debug(
                    "NVMPI probe: nvv4l2decoder not available (%s)",
                    r.stderr.decode()[:200],
                )
            return ok
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.logger.debug("NVMPI probe failed: %s", e)
            return False

    def _use_intel_vaapi(self) -> bool:
        """True if encoding_mode is intel and VA-API device works (device + libva init)."""
        if self._encoding_mode != "intel":
            return False
        if not os.path.exists(VAAPI_DEVICE):
            self.logger.warning(
                "video.encoding=intel but %s not found — recording with CPU. "
                "Для GPU: проверьте runtime: nvidia и devices в compose.",
                VAAPI_DEVICE,
            )
            return False
        if not self._vaapi_checked:
            self._vaapi_checked = True
            self._vaapi_available = self._probe_vaapi()
            if not self._vaapi_available:
                self.logger.warning(
                    "VA-API: %s есть, но init не прошёл — запись на CPU. "
                    "Частая причина: нет group_add групп video/render хоста в compose. "
                    "На сервере: bash scripts/docker-compose-intel-override-gen.sh и пересоздайте контейнер.",
                    VAAPI_DEVICE,
                )
        return self._vaapi_available

    def _use_jetson_nvmpi(self) -> bool:
        """True if on Jetson platform and GStreamer NVMM pipeline works."""
        if self._encoding_mode != "jetson":
            return False
        if not self._nvmpi_checked:
            self._nvmpi_checked = True
            self._nvmpi_available = self._probe_nvmpi()
            if not self._nvmpi_available:
                self.logger.warning(
                    "Jetson NVMPI GStreamer probe failed. "
                    "Check nvidia runtime + gst-inspect-1.0 nvv4l2decoder."
                )
        return self._nvmpi_available

    def start_recording(self, output: str):
        """Start recording: GStreamer on Jetson, FFmpeg otherwise."""
        self._recording = True
        self._reconnect_capture_if_url_changed()
        self._recording_t0 = time.monotonic()
        self._recording_used_vaapi = False
        self._video_output = output
        os.makedirs(os.path.dirname(output), exist_ok=True)
        use_vaapi = self._encoding_mode == "intel" and self._record_with_vaapi and self._use_intel_vaapi()
        if use_vaapi and not self._vaapi_record_available:
            use_vaapi = False
        use_jetson = self._encoding_mode == "jetson"
        if use_jetson and self._record_stream_codec == "h264" and _gst_jetson_record_available():
            cmd = _gst_record_cmd(self.stream_url, output)
            backend_label = "GStreamer OMX (Jetson NVENC)"
        else:
            cmd = _ffmpeg_record_cmd(
                stream_url=self.stream_url,
                output=output,
                use_vaapi=bool(use_vaapi),
                record_stream_codec=self._record_stream_codec,
                encoding_mode=self._encoding_mode,
            )
            if use_jetson and self._record_stream_codec == "h264" and _ffmpeg_has_nvenc():
                backend_label = "FFmpeg NVENC (CUDA)"
            else:
                backend_label = "VA-API" if use_vaapi else "CPU"
        try:
            from encoding_status import set_last_encoding_used

            if use_vaapi:
                self._recording_used_vaapi = True
                set_last_encoding_used("vaapi")
            elif use_jetson and self._record_stream_codec == "h264" and _gst_jetson_record_available():
                set_last_encoding_used("omx")
            elif use_jetson and self._record_stream_codec == "h264" and _ffmpeg_has_nvenc():
                set_last_encoding_used("nvenc")
            elif self._record_stream_codec == "h264" and not use_vaapi:
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
                self._ffmpeg_process.terminate()
                return_code = self._ffmpeg_process.wait(timeout=5)
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
            graceful_sigterm = int(return_code or 0) == 255 and ("Exiting normally, received signal 15." in stderr_text)
            if self._recording_used_vaapi and (return_code is None or (int(return_code) != 0 and not graceful_sigterm)):
                # Quarantine only VA-API recording path after encode failure.
                # Keep capture path independent (it may remain healthy).
                self._vaapi_record_available = False
                _inc_runtime_counter("video_recording_vaapi_fail_total", 1)
                self.logger.error(
                    "VA-API recording failed (ffmpeg rc=%s). Fallback to CPU recording for next clips "
                    "until processor restart/reprobe.",
                    return_code,
                )
            self._ffmpeg_process = None
        self._recording_used_vaapi = False
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
            if (
                self._capture_backend_used == "ffmpeg_vaapi"
                and self._ffmpeg_capture_failures >= FFMPEG_CAPTURE_FAILURE_THRESHOLD
            ):
                self._force_opencv_until_ts = time.time() + float(FFMPEG_CAPTURE_COOLDOWN_SEC)
                self._ffmpeg_capture_failures = 0
                self.logger.warning(
                    "FFmpeg VA-API capture is unstable, forcing OpenCV fallback for %ss",
                    FFMPEG_CAPTURE_COOLDOWN_SEC,
                )
            if (
                self._capture_backend_used == "ffmpeg_nvmpi"
                and self._ffmpeg_capture_failures >= FFMPEG_CAPTURE_FAILURE_THRESHOLD
            ):
                self._force_opencv_until_ts = time.time() + float(FFMPEG_CAPTURE_COOLDOWN_SEC)
                self._ffmpeg_capture_failures = 0
                self._nvmpi_fallback_permanent = True
                self.logger.warning(
                    "GStreamer NVMPI unstable (%d empty reads) — "
                    "permanent fallback to OpenCV for this session",
                    FFMPEG_CAPTURE_FAILURE_THRESHOLD,
                )
            if attempt == 0 and self._reconnect_if_needed():
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
            frame, ok = self._read_frame()
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
