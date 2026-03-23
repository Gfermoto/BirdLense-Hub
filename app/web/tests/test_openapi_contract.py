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
    raw = (
        spec["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]
    )
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
