"""Глобальные обработчики ошибок Flask (#292): единообразный JSON для /api/*."""
from __future__ import annotations

import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException, InternalServerError

_log = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """404/500 для путей API — JSON; остальное — стандартное поведение Werkzeug."""

    @app.errorhandler(404)
    def handle_not_found(exc: HTTPException):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return exc.get_response()

    @app.errorhandler(500)
    def handle_internal_error(exc: BaseException):
        _log.exception('Unhandled server error (path=%s)', request.path)
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        if isinstance(exc, HTTPException):
            return exc.get_response()
        return InternalServerError().get_response()
