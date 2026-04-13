"""
Go2RTC stream source for x86/Docker deployment.
Reads video from RTSP/HLS URL (Go2RTC), supports auto-reconnect, recording via FFmpeg.
Encoding: cpu (copy) or intel (VA-API on any Intel integrated GPU, including Celeron).
"""

import logging
import os
import subprocess
import threading
import time
import cv2

from .streaming_server import start_streaming_server

logger = logging.getLogger(__name__)

VAAPI_DEVICE = "/dev/dri/renderD128"


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

# Reconnect backoff: 1, 2, 4, 8, 16, max 30 sec
MAX_RECONNECT_DELAY = 30
INITIAL_RECONNECT_DELAY = 1


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
    - capture() returns frames for detection (or None on error/reconnect)
    - start_recording/stop_recording uses FFmpeg to record video+audio
    - Auto-reconnect on stream failure
    - Optional MJPEG streaming server for live view
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
    ):
        self.logger = logging.getLogger(__name__)
        self.stream_url = stream_url
        self.main_size = main_size
        self.lores_size = lores_size
        self.auto_reconnect = auto_reconnect
        self._encoding_mode = (encoding_mode or "cpu").strip().lower()
        if self._encoding_mode not in ("cpu", "intel"):
            self._encoding_mode = "cpu"
        rsc = (record_stream_codec or "h264").strip().lower()
        self._record_stream_codec = rsc if rsc in ("h264", "copy") else "h264"

        self._cap = None
        self._out = None
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

        self._connect()

        # Start MJPEG streaming server for live view
        self._streaming_output, self._streaming_thread = start_streaming_server(port=mjpeg_port)

    def _connect(self) -> bool:
        """Open RTSP connection. Returns True if successful."""
        self._disconnect()
        # Не логировать поля из URL (в т.ч. учётка в stream_url) — CodeQL sensitive logging
        self.logger.info("Connecting to video stream (OpenCV)")
        # OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp set in Dockerfile
        cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self.logger.error("Failed to open stream")
            return False
        # Probe FPS
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0:
            self._source_fps = fps
        self._cap = cap
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self.logger.info(f"Connected. FPS: {self._source_fps}")
        return True

    def _disconnect(self):
        """Close RTSP connection."""
        if self._cap:
            self._cap.release()
            self._cap = None

    def _reconnect_if_needed(self) -> bool:
        """Attempt reconnect with backoff. Returns True if connected."""
        if not self.auto_reconnect:
            return False
        while True:
            self.logger.warning(f"Reconnecting in {self._reconnect_delay}s...")
            time.sleep(self._reconnect_delay)
            if self._connect():
                return True
            self._reconnect_delay = min(self._reconnect_delay * 2, MAX_RECONNECT_DELAY)

    def _read_frame(self):
        """Read one frame. Returns (frame_bgr, success)."""
        if not self._cap or not self._cap.isOpened():
            return None, False
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None, False
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
        if use_vaapi:
            cmd = [
                "ffmpeg",
                "-y",
                "-hwaccel",
                "vaapi",
                "-hwaccel_device",
                VAAPI_DEVICE,
                "-hwaccel_output_format",
                "vaapi",
                "-rtsp_transport",
                "tcp",
                "-i",
                self.stream_url,
                "-c:v",
                "h264_vaapi",
                "-b:v",
                "2M",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                output,
            ]
        else:
            # copy: быстрее, но если RTSP/Go2RTC отдаёт HEVC — Chrome/Firefox часто не играют <video>.
            if self._record_stream_codec == "h264":
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-rtsp_transport",
                    "tcp",
                    "-i",
                    self.stream_url,
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
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    output,
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-rtsp_transport",
                    "tcp",
                    "-i",
                    self.stream_url,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    output,
                ]
        try:
            from encoding_status import set_last_encoding_used

            if use_vaapi:
                set_last_encoding_used("vaapi")
            elif self._record_stream_codec == "h264" and not use_vaapi:
                set_last_encoding_used("x264_cpu")
            else:
                set_last_encoding_used("cpu")
        except Exception:
            pass
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
                            lvl = _ffmpeg_stderr_log_level(line)
                            self.logger.log(lvl, "FFmpeg: %s", line)
                except Exception:
                    pass
            self._ffmpeg_process = None
        self.logger.info("Recording stopped")

    def capture(self):
        """
        Get next frame for processing.
        Returns BGR frame resized to lores_size, or None on error.
        """
        with self._read_lock:
            frame, ok = self._read_frame()
        if not ok or frame is None:
            if self._reconnect_if_needed():
                return self.capture()
            return None
        self._frame_count += 1
        self._last_frame_time = time.time()
        frame_lores = cv2.resize(frame, self.lores_size)
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
