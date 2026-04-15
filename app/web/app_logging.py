"""Корневая настройка logging процесса Hub (#292)."""

from __future__ import annotations

import logging
import time
import uuid

from flask import g, has_request_context, request


class RequestContextFilter(logging.Filter):
    """Attach request metadata when logs are emitted inside a Flask request."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = "-"
        record.method = "-"
        record.path = "-"
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.method = request.method
            record.path = request.path
        return True


def configure_process_logging() -> None:
    """Один раз на процесс: консольный handler, формат как раньше в app.py."""
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[request_id=%(request_id)s method=%(method)s path=%(path)s] %(message)s"
        )
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)


def init_request_logging(app) -> None:
    """Assign request ids and emit one concise access log line per request."""

    @app.before_request
    def _assign_request_id() -> None:
        request_id = (request.headers.get("X-Request-ID") or "").strip()
        g.request_id = request_id[:128] if request_id else uuid.uuid4().hex
        g.request_started_at = time.perf_counter()

    @app.after_request
    def _append_request_headers(response):
        request_id = getattr(g, "request_id", "-")
        started_at = getattr(g, "request_started_at", None)
        elapsed_ms = None
        if isinstance(started_at, (int, float)):
            elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        response.headers["X-Request-ID"] = request_id
        app.logger.info(
            "request complete status=%s duration_ms=%s remote_addr=%s",
            response.status_code,
            elapsed_ms if elapsed_ms is not None else "-",
            request.headers.get("X-Real-IP") or request.remote_addr or "-",
        )
        return response
