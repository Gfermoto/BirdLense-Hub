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
