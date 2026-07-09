"""Contract test for GET /api/ui/analytics/trigger-graph."""

from __future__ import annotations


def _auth_headers() -> dict[str, str]:
    import os

    key = (os.environ.get("BIRDLENSE_UI_API_KEY") or os.environ.get("MCP_TOKEN") or "").strip()
    if key:
        return {"X-Birdlense-Api-Key": key}
    return {}


def test_trigger_graph_contract(client, app):
    with app.app_context():
        r = client.get("/api/ui/analytics/trigger-graph?hours=24", headers=_auth_headers())
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert "metrics_by_source" in body
    assert "session_count" in body
    assert "recent_sessions" in body
