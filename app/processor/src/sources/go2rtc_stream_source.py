"""
Go2RTC stream source for x86/Docker deployment.
Reads video from RTSP/HLS URL (Go2RTC), supports auto-reconnect, recording via FFmpeg.
Encoding: cpu (copy) or intel (VA-API on any Intel integrated GPU, including Celeron).
"""
import logging
import os
import subprocess
import time

import cv2

from .streaming_server import start_streaming_server

logger = logging.getLogger(__name__)

VAAPI_DEVICE = "/dev/dri/renderD128"

# Reconnect backoff: 1, 2, 4, 8, 16, max 30 sec
MAX_RECONNECT_DELAY = 30
INITIAL_RECONNECT_DELAY = 1


def _build_stream_url(go2rtc_url: str, stream_name: str, direct_url: str = None,
                      username: str = None, password: str = None) -> str:
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
    ):
        self.logger = logging.getLogger(__name__)
        self.stream_url = stream_url
        self.main_size = main_size
        self.lores_size = lores_size
        self.auto_reconnect = auto_reconnect
        self._encoding_mode = (encoding_mode or "cpu").strip().lower()
        if self._encoding_mode not in ("cpu", "intel"):
            self._encoding_mode = "cpu"

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

        self._connect()

        # Start MJPEG streaming server for live view
        self._streaming_output, self._streaming_thread = start_streaming_server(
            port=mjpeg_port
        )

    def _connect(self) -> bool:
        """Open RTSP connection. Returns True if successful."""
        self._disconnect()
        self.logger.info(f"Connecting to stream: {self.stream_url}")
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
            self._reconnect_delay = min(
                self._reconnect_delay * 2, MAX_RECONNECT_DELAY
            )

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

    def _use_intel_vaapi(self) -> bool:
        """True if encoding_mode is intel and VA-API device is available."""
        if self._encoding_mode != "intel":
            return False
        if not os.path.exists(VAAPI_DEVICE):
            self.logger.warning(
                "video.encoding=intel but %s not found — recording with CPU. "
                "Для GPU: добавьте devices в compose (см. docker-compose.intel.example.yml).",
                VAAPI_DEVICE,
            )
            return False
        return True

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
                "-hwaccel", "vaapi",
                "-hwaccel_device", VAAPI_DEVICE,
                "-hwaccel_output_format", "vaapi",
                "-rtsp_transport", "tcp",
                "-i", self.stream_url,
                "-c:v", "h264_vaapi",
                "-b:v", "2M",
                "-c:a", "aac",
                "-movflags", "+faststart",
                output,
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-rtsp_transport", "tcp",
                "-i", self.stream_url,
                "-c:v", "copy",
                "-c:a", "aac",
                "-movflags", "+faststart",
                output,
            ]
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
            except Exception as e:
                self.logger.warning(f"Error stopping FFmpeg: {e}")
            self._ffmpeg_process = None
        self.logger.info("Recording stopped")

    def capture(self):
        """
        Get next frame for processing.
        Returns BGR frame resized to lores_size, or None on error.
        """
        frame, ok = self._read_frame()
        if not ok or frame is None:
            if self._reconnect_if_needed():
                return self.capture()
            return None

        self._frame_count += 1
        self._last_frame_time = time.time()

        # Resize for detection (frame is already BGR from VideoCapture)
        frame_lores = cv2.resize(frame, self.lores_size)

        # Update live stream
        self._update_streaming_output(frame)

        return frame_lores

    def close(self):
        """Release resources."""
        self.stop_recording()
        self._disconnect()
        if self._streaming_output:
            self._streaming_output.close()
