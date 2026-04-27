"""BIRDLENSE_STRICT_API_AUTH + production: закрытие анонимного доступа к /api/ui/* (#279)."""

import pytest


@pytest.fixture
def _strict_prod_env(monkeypatch):
    monkeypatch.setenv("BIRDLENSE_ENV", "production")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("BIRDLENSE_STRICT_API_AUTH", "1")


def test_strict_flag_without_production_does_not_block_public_ui_api(client, monkeypatch):
    """Флаг без production-рантайма не меняет поведение (LAN / тесты)."""
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("BIRDLENSE_STRICT_API_AUTH", "1")
    r = client.get("/api/ui/species")
    assert r.status_code == 200


def test_production_strict_blocks_species_list_without_session(client, _strict_prod_env):
    r = client.get("/api/ui/species")
    assert r.status_code == 403
    assert r.get_json().get("error") == "Authentication required"


def test_production_strict_allows_bootstrap_endpoints(client, _strict_prod_env):
    assert client.get("/api/ui/health").status_code == 200
    assert client.get("/api/ui/readiness").status_code == 200
    csrf = client.get("/api/ui/csrf-token")
    assert csrf.status_code == 200
    token = csrf.get_json()["csrf_token"]
    assert client.get("/api/ui/settings/requires-password").status_code == 200
    assert client.get("/api/ui/settings/check-access").status_code == 200
    r = client.post(
        "/api/ui/settings/verify-password",
        json={"password": ""},
        headers={"X-Birdlense-CSRF-Token": token},
    )
    assert r.status_code in (200, 401)


def test_production_strict_allows_ui_api_key_header(client, _strict_prod_env, monkeypatch):
    monkeypatch.setenv("BIRDLENSE_UI_API_KEY", "test-ui-key-279")
    r = client.get("/api/ui/species", headers={"X-Birdlense-Api-Key": "test-ui-key-279"})
    assert r.status_code == 200


def test_production_strict_allows_bearer_ui_api_key(client, _strict_prod_env, monkeypatch):
    monkeypatch.setenv("BIRDLENSE_UI_API_KEY", "bearer-key-279")
    r = client.get(
        "/api/ui/species",
        headers={"Authorization": "Bearer bearer-key-279"},
    )
    assert r.status_code == 200


def test_production_strict_allows_mcp_bearer(client, _strict_prod_env, monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "mcp-secret-279")
    r = client.get(
        "/api/ui/overview",
        headers={"Authorization": "Bearer mcp-secret-279"},
    )
    assert r.status_code == 200


def test_options_preflight_not_blocked(client, _strict_prod_env):
    r = client.open("/api/ui/species", method="OPTIONS")
    assert r.status_code in (200, 404, 405)


def test_strict_gate_only_under_api_ui_prefix(client, _strict_prod_env, monkeypatch):
    """Префикс /api/metrics не проходит через strict-ui middleware."""
    monkeypatch.delenv("BIRDLENSE_METRICS_TOKEN", raising=False)
    r = client.get("/api/metrics")
    assert r.status_code == 200


def test_session_unlock_allows_timeline(client, monkeypatch, _strict_prod_env):
    from app_config.app_config import app_config

    general = dict(app_config.config.get("general") or {})
    general["settings_password"] = "hub-secret-279"
    general["contributor_password"] = ""
    monkeypatch.setitem(app_config.config, "general", general)
    csrf = client.get("/api/ui/csrf-token").get_json()["csrf_token"]
    assert (
        client.post(
            "/api/ui/settings/verify-password",
            json={"password": "hub-secret-279"},
            headers={"X-Birdlense-CSRF-Token": csrf},
        ).status_code
        == 200
    )
    assert client.get("/api/ui/species").status_code == 200
