"""Retention API defaults must match default_config.yaml (#615)."""

from __future__ import annotations

from pathlib import Path

import yaml

from app_config.app_config import app_config


def _default_retention_yaml() -> dict:
    path = Path(__file__).resolve().parents[2] / "app_config" / "default_config.yaml"
    root = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    section = root.get("retention") if isinstance(root, dict) else {}
    return section if isinstance(section, dict) else {}


P0_RETENTION_KEYS = (
    "mode",
    "days",
    "max_gb",
    "auto_run_enabled",
    "auto_run_interval_hours",
    "protect_favorites",
    "min_age_hours",
    "batch_size",
    "max_deletes_per_run",
)


def test_build_retention_safe_public_config_matches_default_yaml(app):
    defaults = _default_retention_yaml()
    with app.app_context():
        safe = app_config.build_retention_safe_public_config()
    for key in P0_RETENTION_KEYS:
        assert safe.get(key) == defaults.get(key), (
            f"retention.{key}: API={safe.get(key)!r} default_config={defaults.get(key)!r}"
        )


def test_retention_get_api_matches_default_yaml(client, app):
    defaults = _default_retention_yaml()
    old_admin = app_config.get("general.settings_password")
    old_contrib = app_config.get("general.contributor_password")
    old_auto = app_config.get("retention.auto_run_enabled")
    try:
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")
        res = client.get("/api/ui/system/retention")
        assert res.status_code == 200, res.get_data(as_text=True)
        payload = res.get_json() or {}
        assert payload.get("auto_run_enabled") is defaults.get("auto_run_enabled")
        assert payload.get("auto_run_interval_hours") == defaults.get("auto_run_interval_hours")
        assert payload.get("days") == defaults.get("days")
    finally:
        if old_auto is not None:
            app_config.set("retention.auto_run_enabled", old_auto)
        app_config.set("general.settings_password", old_admin)
        app_config.set("general.contributor_password", old_contrib)


def test_retention_put_response_auto_run_default_false(client, app, tmp_path, monkeypatch):
    """PUT partial update must not imply auto_run_enabled=true when key absent."""
    defaults = _default_retention_yaml()
    user_path = tmp_path / "user_config.yaml"
    user_path.write_text("retention:\n  days: 30\n", encoding="utf-8")
    monkeypatch.setattr(app_config, "user_config_file", str(user_path))
    app_config.reload()

    old_admin = app_config.get("general.settings_password")
    try:
        app_config.set("general.settings_password", "")
        res = client.put(
            "/api/ui/system/retention",
            json={"days": 45},
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 200, res.get_data(as_text=True)
        payload = res.get_json() or {}
        assert payload.get("auto_run_enabled") is defaults.get("auto_run_enabled")
        assert payload.get("days") == 45
    finally:
        app_config.set("general.settings_password", old_admin)
        app_config.reload()
