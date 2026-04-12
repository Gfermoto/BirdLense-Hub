"""Юнит-тесты декораторов routes/http_guards.py (#302)."""

from __future__ import annotations


def test_require_ui_settings_password_denied(monkeypatch):
    import auth

    monkeypatch.setattr(auth, "settings_check_access", lambda: False)
    from routes.http_guards import require_ui_settings_password

    @require_ui_settings_password
    def view():
        return {"ok": True}, 200

    body, code = view()
    assert code == 403
    assert body == {"error": "Password required"}


def test_require_ui_settings_unauthorized_denied(monkeypatch):
    import auth

    monkeypatch.setattr(auth, "settings_check_access", lambda: False)
    from routes.http_guards import require_ui_settings_unauthorized

    @require_ui_settings_unauthorized
    def view():
        return {"x": 1}, 200

    body, code = view()
    assert code == 401
    assert body == {"error": "Unauthorized"}


def test_require_admin_track_regen_denied(monkeypatch):
    import auth

    monkeypatch.setattr(auth, "admin_track_regen_access", lambda: False)
    from routes.http_guards import require_admin_track_regen

    @require_admin_track_regen
    def view():
        return {"ok": True}, 200

    body, code = view()
    assert code == 403
    assert body == {"error": "Access denied"}


def test_decorators_allow_when_auth_ok(monkeypatch):
    import auth

    monkeypatch.setattr(auth, "settings_check_access", lambda: True)
    monkeypatch.setattr(auth, "admin_track_regen_access", lambda: True)
    from routes.http_guards import (
        require_admin_track_regen,
        require_ui_settings_password,
        require_ui_settings_unauthorized,
    )

    @require_ui_settings_password
    def v1():
        return {"a": 1}, 200

    @require_ui_settings_unauthorized
    def v2():
        return {"b": 2}, 200

    @require_admin_track_regen
    def v3():
        return {"c": 3}, 200

    assert v1() == ({"a": 1}, 200)
    assert v2() == ({"b": 2}, 200)
    assert v3() == ({"c": 3}, 200)
