"""Глобальные обработчики ошибок Flask (#292): единообразный JSON для /api/*."""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException, InternalServerError

_log = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """HTTP-исключения и 500 для /api/* — JSON; остальное — стандартное поведение Werkzeug."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        if request.path.startswith("/api/"):
            msg = (exc.description or "").strip() or exc.name
            return jsonify({"error": msg}), exc.code
        return exc.get_response()

    @app.errorhandler(500)
    def handle_internal_error(exc: BaseException):
        _log.exception("Unhandled server error (path=%s)", request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return InternalServerError().get_response()
