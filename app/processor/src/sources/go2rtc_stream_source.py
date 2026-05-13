"""
Go2RTC stream source for x86/Docker deployment.
Reads video from RTSP/HLS URL (Go2RTC), supports auto-reconnect, recording via FFmpeg.
Encoding: cpu (copy) or intel (VA-API on any Intel integrated GPU, including Celeron).
"""

import logging
import os
import re
import subprocess
import threading
import time
import cv2
import numpy as np

from yolo_geometry import letterbox_bgr_to_wh

from .streaming_server import start_streaming_server

logger = logging.getLogger(__name__)

VAAPI_DEVICE = "/dev/dri/renderD128"


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
    if backend in ("auto", "opencv", "ffmpeg_vaapi"):
        return backend
    return "auto"


def _capture_fallback_reason(
    *,
    requested_backend: str,
    encoding_mode: str,
    vaapi_available: bool,
) -> str:
    """Classify fallback reason for capture backend telemetry."""
    rb = _normalize_capture_backend(requested_backend)
    enc = (encoding_mode or "cpu").strip().lower()
    if rb == "opencv":
        return "requested_opencv"
    if rb == "ffmpeg_vaapi" and not vaapi_available:
        return "vaapi_unavailable"
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


def _ffmpeg_record_cmd(
    *,
    stream_url: str,
    output: str,
    use_vaapi: bool,
    record_stream_codec: str,
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
        cmd += [
            "-hwaccel",
            "vaapi",
            "-hwaccel_device",
            VAAPI_DEVICE,
            "-hwaccel_output_format",
            "vaapi",
        ]
    cmd += [
        "-rtsp_transport",
        "tcp",
        "-i",
        stream_url,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
    ]
    if use_vaapi:
        cmd += [
            "-c:v",
            "h264_vaapi",
            "-b:v",
            "2M",
        ]
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
        main_size=(1280, 720),
        lores_size=(640, 640),
        auto_reconnect=True,
        pre_record_seconds=0,
        mjpeg_port=8082,
        encoding_mode="cpu",
        record_stream_codec="h264",
        capture_backend="auto",
        capture_stream_url: str | None = None,
    ):
        self.logger = logging.getLogger(__name__)
        # Main/high stream: FFmpeg recording only.
        self.stream_url = stream_url
        # Optional second RTSP (e.g. Go2RTC name for camera sub / Frigate detect) — lower res & FPS.
        self._capture_stream_url = (capture_stream_url or "").strip() or stream_url
        self.main_size = main_size
        self.lores_size = lores_size
        self.auto_reconnect = auto_reconnect
        self._encoding_mode = (encoding_mode or "cpu").strip().lower()
        if self._encoding_mode not in ("cpu", "intel"):
            self._encoding_mode = "cpu"
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
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self._last_frame_time = 0
        self._frame_count = 0
        self._source_fps = 15.0
        self._read_lock = threading.Lock()
        self._vaapi_checked = False
        self._vaapi_available = True
        self._ffmpeg_capture_failures = 0
        self._force_opencv_until_ts = 0.0

        if self._capture_stream_url != self.stream_url:
            self.logger.info(
                "Go2RTC dual-stream: capture (motion/YOLO/MJPEG) ≠ record (main RTSP). "
                "YOLO still gets letterbox to inference size after decode."
            )

        self._connect()

        # Start MJPEG streaming server for live view
        self._streaming_output, self._streaming_thread = start_streaming_server(port=mjpeg_port)

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
        # Не логировать поля из URL (в т.ч. учётка в stream_url) — CodeQL sensitive logging
        self.logger.info("Connecting to video stream (OpenCV, capture/detect)")
        # OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp set in Dockerfile
        cap = cv2.VideoCapture(self._capture_stream_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self.logger.error("Failed to open stream")
            return False
        # Probe FPS
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0:
            self._source_fps = fps
        self._cap = cap
        self._capture_backend_used = "opencv"
        _set_runtime_gauge("video_capture_backend_used", self._capture_backend_used)
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self.logger.info(f"Connected. FPS: {self._source_fps}")
        return True

    def _should_use_ffmpeg_vaapi_capture(self) -> bool:
        """Whether live inference capture should try FFmpeg VA-API."""
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
        cmd = _ffmpeg_vaapi_capture_cmd(self._capture_stream_url, self.lores_size)
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
        self.logger.info("Connected. Capture backend: FFmpeg VA-API")
        return True

    def _disconnect(self):
        """Close RTSP connection."""
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
                return True
            self._reconnect_delay = min(self._reconnect_delay * 2, MAX_RECONNECT_DELAY)

    def _read_frame(self):
        """Read one frame. Returns (frame_bgr, success)."""
        if self._capture_backend_used == "ffmpeg_vaapi":
            return self._read_ffmpeg_vaapi_frame()
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

    def _update_streaming_output(self, frame):
        """Push frame to MJPEG streaming server."""
        if self._streaming_output and frame is not None:
            _, jpeg = cv2.imencode(".jpg", frame)
            if jpeg is not None:
                self._streaming_output.write(jpeg.tobytes())

    def _probe_vaapi(self) -> bool:
        """Check if VA-API actually works in this container (libva/driver)."""
        try:
            r = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-hwaccel",
                    "vaapi",
                    "-hwaccel_device",
                    VAAPI_DEVICE,
                    "-hwaccel_output_format",
                    "vaapi",
                    "-f",
                    "lavfi",
                    "-i",
                    "nullsrc=d=1",
                    "-t",
                    "0.01",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                timeout=10,
            )
            if r.returncode != 0 and r.stderr:
                self.logger.debug("VA-API probe stderr: %s", r.stderr.decode("utf-8", errors="replace")[:300])
            return r.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.logger.debug("VA-API probe failed: %s", e)
            return False

    def _use_intel_vaapi(self) -> bool:
        """True if encoding_mode is intel and VA-API device works (device + libva init)."""
        if self._encoding_mode != "intel":
            return False
        if not os.path.exists(VAAPI_DEVICE):
            self.logger.warning(
                "video.encoding=intel but %s not found — recording with CPU. "
                "Для GPU: добавьте devices в compose (см. docker-compose.intel.example.yml).",
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

    def start_recording(self, output: str):
        """Start recording via FFmpeg (video+audio from RTSP). CPU or Intel VA-API."""
        self._recording = True
        self._video_output = output
        os.makedirs(os.path.dirname(output), exist_ok=True)
        use_vaapi = self._use_intel_vaapi()
        cmd = _ffmpeg_record_cmd(
            stream_url=self.stream_url,
            output=output,
            use_vaapi=bool(use_vaapi),
            record_stream_codec=self._record_stream_codec,
        )
        try:
            from encoding_status import set_last_encoding_used

            if use_vaapi:
                set_last_encoding_used("vaapi")
            elif self._record_stream_codec == "h264" and not use_vaapi:
                set_last_encoding_used("x264_cpu")
            else:
                set_last_encoding_used("cpu")
        except Exception:
            self.logger.debug("encoding_status recording path failed", exc_info=True)
        self.logger.info(
            "Starting FFmpeg recording to %s (%s)",
            output,
            "VA-API" if use_vaapi else "CPU",
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
        if self._ffmpeg_process:
            try:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ffmpeg_process.kill()
                self._ffmpeg_process.wait(timeout=2)
            except Exception as e:
                self.logger.warning("Error stopping FFmpeg: %s", e)
            if self._ffmpeg_process and self._ffmpeg_process.stderr:
                try:
                    err = self._ffmpeg_process.stderr.read()
                    if err:
                        for line in err.decode("utf-8", errors="replace").strip().splitlines():
                            safe = _sanitize_ffmpeg_stderr_line(line)
                            lvl = _ffmpeg_stderr_log_level(safe)
                            self.logger.log(lvl, "FFmpeg: %s", safe)
                except Exception:
                    self.logger.debug("FFmpeg stderr drain failed", exc_info=True)
            self._ffmpeg_process = None
        self.logger.info("Recording stopped")

    def capture(self):
        """
        Get next frame for processing.
        Returns BGR frame resized to lores_size, or None on error.
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
            if attempt == 0 and self._reconnect_if_needed():
                continue
            return None
        self._frame_count += 1
        self._last_frame_time = time.time()
        if self._capture_backend_used == "ffmpeg_vaapi":
            frame_lores = frame
        else:
            frame_lores = letterbox_bgr_to_wh(
                frame,
                (int(self.lores_size[0]), int(self.lores_size[1])),
            )
        self._update_streaming_output(frame)
        return frame_lores

    def push_one_frame_to_mjpeg(self):
        """Read one frame and push to MJPEG (for live view). Skips if main thread is reading."""
        if not self._streaming_output:
            return
        if not self._read_lock.acquire(blocking=False):
            return
        try:
            frame, ok = self._read_frame()
            if ok and frame is not None:
                self._update_streaming_output(frame)
        finally:
            self._read_lock.release()

    def close(self):
        """Release resources."""
        self.stop_recording()
        self._disconnect()
        if self._streaming_output:
            self._streaming_output.close()
