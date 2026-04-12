"""Юнит-тесты services.settings_access_service (#293)."""


def test_gate_no_passwords_non_prod_false(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    from app_config.app_config import app_config
    from services.settings_access_service import settings_gate_requires_password

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, "settings_password", "")
    monkeypatch.setitem(gen, "contributor_password", "")
    assert settings_gate_requires_password() is False


def test_gate_no_passwords_prod_true(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    from app_config.app_config import app_config
    from services.settings_access_service import settings_gate_requires_password

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, "settings_password", "")
    monkeypatch.setitem(gen, "contributor_password", "")
    try:
        assert settings_gate_requires_password() is True
    finally:
        monkeypatch.delenv("FLASK_ENV", raising=False)


def test_gate_any_password_true(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    from app_config.app_config import app_config
    from services.settings_access_service import settings_gate_requires_password

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, "settings_password", "x")
    monkeypatch.setitem(gen, "contributor_password", "")
    assert settings_gate_requires_password() is True


def test_resolve_unlock_admin_contributor_nomatch(monkeypatch):
    from app_config.app_config import app_config
    from services.settings_access_service import resolve_password_unlock_role

    g = app_config.config.setdefault("general", {})
    monkeypatch.setitem(g, "settings_password", "adm")
    monkeypatch.setitem(g, "contributor_password", "ctr")
    assert resolve_password_unlock_role("adm") == "admin"
    assert resolve_password_unlock_role("ctr") == "contributor"
    assert resolve_password_unlock_role("wrong") is None


def test_empty_passwords_block_in_prod(monkeypatch):
    monkeypatch.setenv("BIRDLENSE_ENV", "production")
    from app_config.app_config import app_config
    from services.settings_access_service import (
        empty_passwords_block_verify_in_production,
    )

    g = app_config.config.setdefault("general", {})
    monkeypatch.setitem(g, "settings_password", "")
    monkeypatch.setitem(g, "contributor_password", "")
    try:
        assert empty_passwords_block_verify_in_production() is True
    finally:
        monkeypatch.delenv("BIRDLENSE_ENV", raising=False)


def test_empty_passwords_allow_outside_prod(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    from app_config.app_config import app_config
    from services.settings_access_service import (
        empty_passwords_block_verify_in_production,
    )

    g = app_config.config.setdefault("general", {})
    monkeypatch.setitem(g, "settings_password", "")
    monkeypatch.setitem(g, "contributor_password", "")
    assert empty_passwords_block_verify_in_production() is False
