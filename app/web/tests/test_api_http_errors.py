"""Единый JSON для HTTP-ошибок на путях /api/* (#292, PR #301)."""

from __future__ import annotations


def test_api_unknown_path_returns_json_404(client):
    r = client.get("/api/__birdlense_no_such_route__")
    assert r.status_code == 404
    data = r.get_json()
    assert isinstance(data, dict)
    assert "error" in data


def test_non_api_404_not_forced_to_json(client):
    r = client.get("/__birdlense_no_such_page__")
    assert r.status_code == 404
    # Werkzeug HTML по умолчанию, не наш JSON-обёртка
    assert not r.is_json


def test_api_method_not_allowed_returns_json(client):
    r = client.post("/api/ui/health")
    assert r.status_code == 405
    data = r.get_json()
    assert isinstance(data, dict)
    assert "error" in data


def test_api_request_id_header_is_generated(client):
    r = client.get("/api/ui/health")
    assert r.status_code == 200
    assert isinstance(r.headers.get("X-Request-ID"), str)
    assert len(r.headers["X-Request-ID"]) >= 8


def test_api_request_id_header_preserves_client_value(client):
    r = client.get("/api/ui/health", headers={"X-Request-ID": "ci-request-123"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == "ci-request-123"
