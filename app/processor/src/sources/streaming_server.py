"""
MJPEG streaming server for live video view.
Used by Go2RTCStreamSource when running in processor.
"""
import io
import logging
import socketserver
from http import server
from threading import Condition, Thread

logger = logging.getLogger(__name__)


class StreamingOutput(io.BufferedIOBase):
    """Thread-safe buffer for MJPEG frames."""

    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf: bytes) -> int:
        with self.condition:
            self.frame = buf
            self.condition.notify_all()
        return len(buf)

    def close(self):
        pass


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()
            output = self.server.streaming_output
            while True:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                if frame is None:
                    break
                self.wfile.write(b"--FRAME\r\n")
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.debug(f"Client disconnected: {e}")
        except Exception as e:
            logger.warning(f"Stream error: {e}")

    def log_message(self, format, *args):
        logger.debug(f"MJPEG {args[0]}")


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_streaming_server(port: int = 8082):
    """Start MJPEG streaming server. Returns (StreamingOutput, thread)."""
    output = StreamingOutput()
    # 0.0.0.0: MJPEG для nginx в контейнере, не публичный bind с хоста
    server = StreamingServer(("0.0.0.0", port), StreamingHandler)  # nosec B104
    server.streaming_output = output

    def serve():
        try:
            server.serve_forever()
        except Exception as e:
            logger.error(f"Streaming server error: {e}")
        finally:
            server.shutdown()

    thread = Thread(target=serve, daemon=True)
    thread.start()
    logger.info(f"MJPEG streaming server started on port {port}")
    return output, thread
