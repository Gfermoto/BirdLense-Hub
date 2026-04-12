"""Optional Bearer gate for Prometheus and JSON metrics (#222)."""

from __future__ import annotations

import hmac
import os


def metrics_bearer_denied(*, prometheus: bool = False):
    """Require Bearer if ``BIRDLENSE_METRICS_TOKEN`` set; else None (allow)."""
    from flask import Response, jsonify, request

    expected = (os.environ.get("BIRDLENSE_METRICS_TOKEN") or "").strip()
    if not expected:
        return None
    auth = (request.headers.get("Authorization") or "").strip()
    scheme, _, credentials = auth.partition(" ")
    got = credentials.strip() if scheme.lower() == "bearer" else ""
    if got and hmac.compare_digest(got, expected):
        return None
    if prometheus:
        return Response(
            "# Unauthorized\n",
            status=401,
            mimetype="text/plain; charset=utf-8",
        )
    return jsonify({"error": "Unauthorized"}), 401
