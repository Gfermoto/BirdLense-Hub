"""OpenAPI contract smoke tests against Flask test client responses."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.yaml"


def _load_spec() -> dict[str, Any]:
    with OPENAPI_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_ref(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    # Supports local refs like "#/components/schemas/OverviewStats".
    node: Any = spec
    for part in ref.removeprefix("#/").split("/"):
        node = node[part]
    return node


def _schema_for(
    spec: dict[str, Any],
    *,
    path: str,
    method: str = "get",
    status: str = "200",
) -> dict[str, Any]:
    raw = spec["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]
    return _resolve_ref(spec, raw)


def _assert_matches_schema(spec: dict[str, Any], value: Any, schema: dict[str, Any]) -> None:
    schema = _resolve_ref(spec, schema)
    expected_type = schema.get("type")

    if expected_type == "object":
        assert isinstance(value, dict)
        required = schema.get("required", [])
        for key in required:
            assert key in value, f"Missing required key: {key}"
        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in value and value[key] is not None:
                _assert_matches_schema(spec, value[key], prop_schema)
        return

    if expected_type == "array":
        assert isinstance(value, list)
        item_schema = schema.get("items", {})
        # Smoke-level validation: validate up to first 10 items.
        for item in value[:10]:
            if item is not None:
                _assert_matches_schema(spec, item, item_schema)
        return

    if expected_type == "string":
        assert isinstance(value, str)
        return

    if expected_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool)
        return

    if expected_type == "number":
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
        return

    if expected_type == "boolean":
        assert isinstance(value, bool)
        return

    # Unknown/omitted type in schema -> keep smoke test permissive.


class TestOpenApiContractSmoke:
    """Contract smoke tests for stable, unauthenticated GET endpoints."""

    def test_health_matches_openapi_schema(self, client):
        spec = _load_spec()
        response = client.get("/api/ui/health")
        assert response.status_code == 200
        schema = _schema_for(spec, path="/health")
        _assert_matches_schema(spec, response.json, schema)

    def test_readiness_matches_openapi_schema(self, client):
        spec = _load_spec()
        response = client.get("/api/ui/readiness")
        assert response.status_code == 200
        schema = _schema_for(spec, path="/readiness")
        _assert_matches_schema(spec, response.json, schema)

    def test_readiness_503_matches_openapi_schema(self, client, monkeypatch):
        spec = _load_spec()
        from models import db

        def _boom(*_args, **_kwargs):
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(db.session, "execute", _boom)
        response = client.get("/api/ui/readiness")
        assert response.status_code == 503
        schema = _schema_for(spec, path="/readiness", status="503")
        _assert_matches_schema(spec, response.json, schema)

    def test_species_matches_openapi_schema(self, client):
        spec = _load_spec()
        response = client.get("/api/ui/species")
        assert response.status_code == 200
        schema = _schema_for(spec, path="/species")
        _assert_matches_schema(spec, response.json, schema)

    def test_bird_families_matches_openapi_schema(self, client):
        spec = _load_spec()
        response = client.get("/api/ui/bird_families")
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            schema = _schema_for(spec, path="/bird_families")
        else:
            schema = _schema_for(spec, path="/bird_families", status="404")
        _assert_matches_schema(spec, response.json, schema)

    def test_overview_matches_openapi_schema(self, client):
        spec = _load_spec()
        today = datetime.now(timezone.utc).date().isoformat()
        response = client.get("/api/ui/overview", query_string={"date": today})
        assert response.status_code == 200
        schema = _schema_for(spec, path="/overview")
        _assert_matches_schema(spec, response.json, schema)

    def test_unknowns_matches_openapi_schema(self, client):
        spec = _load_spec()
        now_ts = int(datetime.now(timezone.utc).timestamp())
        response = client.get(
            "/api/ui/unknowns",
            query_string={
                "start_time": now_ts - 3600,
                "end_time": now_ts,
                "limit": 10,
            },
        )
        assert response.status_code == 200
        schema = _schema_for(spec, path="/unknowns")
        _assert_matches_schema(spec, response.json, schema)

    def test_video_neighbors_matches_openapi_schema(self, app, client):
        spec = _load_spec()
        from models import Video, db

        with app.app_context():
            v = Video(
                processor_version="openapi",
                start_time=datetime(2026, 4, 6, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 6, 14, 5, 0, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/06/140000/video.mp4",
            )
            db.session.add(v)
            db.session.commit()
            vid = v.id

        response = client.get(f"/api/ui/videos/{vid}/neighbors")
        assert response.status_code == 200
        schema = _schema_for(spec, path="/videos/{video_id}/neighbors")
        _assert_matches_schema(spec, response.json, schema)

    def test_video_fusion_trace_matches_openapi_schema(self, app, client):
        spec = _load_spec()
        from models import Video, db

        with app.app_context():
            v = Video(
                processor_version="openapi",
                start_time=datetime(2026, 4, 10, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 10, 14, 5, 0, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/10/fusion-openapi.mp4",
            )
            db.session.add(v)
            db.session.commit()
            vid = v.id

        with client.session_transaction() as sess:
            sess["access_role"] = "contributor"
        response = client.get(f"/api/ui/videos/{vid}/fusion-trace")
        assert response.status_code == 200
        schema = _schema_for(spec, path="/videos/{video_id}/fusion-trace")
        _assert_matches_schema(spec, response.json, schema)

    def test_system_config_audit_matches_openapi_schema(self, client):
        spec = _load_spec()
        with client.session_transaction() as sess:
            sess["access_role"] = "admin"
            sess["settings_unlocked"] = True
        response = client.get("/api/ui/system/config-audit")
        assert response.status_code == 200
        schema = _schema_for(spec, path="/system/config-audit")
        _assert_matches_schema(spec, response.json, schema)
