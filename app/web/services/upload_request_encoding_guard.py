"""Ограничение Content-Encoding на upload-роутах (#341).

Классический риск: маленький gzip/deflate/brotli body с огромным распакованным
объёмом (bomb), если где-то в цепочке прозрачно декодируют тело запроса.
Браузеры при multipart/file не выставляют Content-Encoding на сжатие тела;
нормальный клиент загружает сырой multipart.
"""

from __future__ import annotations

from flask import Flask, jsonify, request

# Пути: multipart / файлы (см. routes/* upload, yaml-import).
_UPLOAD_PATHS: frozenset[str] = frozenset(
    {
        "/api/ui/system/file-test/upload",
        "/api/ui/system/db/restore",
        "/api/ui/settings/yaml-import",
    }
)


def _content_encoding_tokens() -> list[str]:
    raw = (request.headers.get("Content-Encoding") or "").strip()
    if not raw:
        return []
    out: list[str] = []
    for part in raw.split(","):
        p = part.split(";", 1)[0].strip().lower()
        if p:
            out.append(p)
    return out


def register_upload_request_encoding_guard(app: Flask) -> None:
    """Зарегистрировать before_request: отсечь сжатые тела на upload-URL."""

    @app.before_request
    def _reject_compressed_upload_encoding():
        if request.method != "POST":
            return None
        if (request.path or "") not in _UPLOAD_PATHS:
            return None
        tokens = _content_encoding_tokens()
        if not tokens:
            return None
        if tokens == ["identity"]:
            return None
        detail = (
            "Do not send gzip/deflate/brotli (or stacked encodings) on file "
            "upload requests; send uncompressed multipart."
        )
        return (
            jsonify(
                {
                    "error": "Unsupported Content-Encoding on upload",
                    "detail": detail,
                }
            ),
            415,
        )
