"""Smoke tests for settings-gated POST/PATCH (issue #202)."""

from datetime import datetime, timezone


def _patch_general_key(monkeypatch, key: str, value):
    """Patch a key inside merged ``general`` (user_config may set passwords)."""
    from app_config.app_config import app_config

    gen = app_config.config.setdefault("general", {})
    monkeypatch.setitem(gen, key, value)


def _open_settings_access(monkeypatch):
    """Empty passwords allow access only outside production (see ``auth.settings_check_access``)."""
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    _patch_general_key(monkeypatch, "settings_password", "")
    _patch_general_key(monkeypatch, "contributor_password", "")


def test_birdfood_post_forbidden_when_settings_locked(client, monkeypatch):
    _patch_general_key(monkeypatch, "settings_password", "integration-test-lock")
    _patch_general_key(monkeypatch, "contributor_password", "")

    r = client.post(
        "/api/ui/birdfood",
        json={"name": "Should Not Be Created"},
        content_type="application/json",
    )
    assert r.status_code == 403


def test_birdfood_post_and_toggle_happy_path(app, client, monkeypatch):
    _open_settings_access(monkeypatch)
    unique = f"CI Birdfood {id(app)}"

    r = client.post(
        "/api/ui/birdfood",
        json={"name": unique, "active": True},
        content_type="application/json",
    )
    assert r.status_code == 201

    lst = client.get("/api/ui/birdfood").get_json()
    assert isinstance(lst, list)
    row = next((x for x in lst if x["name"] == unique), None)
    assert row is not None
    assert row["active"] is True
    bid = row["id"]

    r2 = client.patch(f"/api/ui/birdfood/{bid}/toggle")
    assert r2.status_code == 200

    lst2 = client.get("/api/ui/birdfood").get_json()
    row2 = next(x for x in lst2 if x["id"] == bid)
    assert row2["active"] is False

    with app.app_context():
        from models import BirdFood, db

        db.session.delete(db.session.get(BirdFood, bid))
        db.session.commit()


def test_birdfood_post_duplicate_name_400(app, client, monkeypatch):
    _open_settings_access(monkeypatch)
    unique = f"Dup Birdfood {id(app)}"

    assert (
        client.post(
            "/api/ui/birdfood",
            json={"name": unique},
            content_type="application/json",
        ).status_code
        == 201
    )

    r = client.post(
        "/api/ui/birdfood",
        json={"name": unique},
        content_type="application/json",
    )
    assert r.status_code == 400

    with app.app_context():
        from models import BirdFood, db

        bf = BirdFood.query.filter_by(name=unique).first()
        if bf:
            db.session.delete(bf)
            db.session.commit()


def test_push_subscribe_success_when_notifications_on(app, client, monkeypatch):
    from app_config.app_config import app_config

    _open_settings_access(monkeypatch)
    _patch_general_key(monkeypatch, "enable_notifications", True)
    monkeypatch.setattr(app_config, "save", lambda: None)

    ep = f"https://example.test/push/ep-{id(app)}"
    r = client.post(
        "/api/ui/push/subscribe",
        json={
            "subscription": {
                "endpoint": ep,
                "keys": {"p256dh": "k" * 8, "auth": "a" * 8},
            },
        },
        content_type="application/json",
    )
    assert r.status_code in (200, 201)

    with app.app_context():
        from models import PushSubscription, db

        row = PushSubscription.query.filter_by(endpoint=ep).first()
        assert row is not None
        db.session.delete(row)
        db.session.commit()


def test_video_stream_allows_contributor_when_stream_auth_required(
    app,
    client,
    tmp_path,
    monkeypatch,
):
    """require_auth_for_video_stream + пароли: гость 403, contributor 200."""
    from models import Video, db

    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)

    fake = tmp_path / "stream-smoke.mp4"
    fake.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2")
    monkeypatch.setattr("util.full_path_for_video", lambda _p: str(fake))

    vp = "data/recordings/2026/04/03/140000/video.mp4"
    with app.app_context():
        v = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path=vp,
        )
        db.session.add(v)
        db.session.commit()
        vid = v.id

    _patch_general_key(monkeypatch, "require_auth_for_video_stream", True)
    _patch_general_key(monkeypatch, "settings_password", "stream-gate-pw")
    _patch_general_key(monkeypatch, "contributor_password", "")

    assert client.get(f"/api/ui/videos/{vid}/stream").status_code == 403

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"

    r = client.get(f"/api/ui/videos/{vid}/stream")
    assert r.status_code == 200
    assert "video" in (r.content_type or "").lower()

    with app.app_context():
        db.session.delete(db.session.get(Video, vid))
        db.session.commit()


def test_settings_logout_clears_session(client, monkeypatch):
    """POST /api/ui/settings/logout сбрасывает access_role для следующего входа."""
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    _patch_general_key(monkeypatch, "settings_password", "x")
    _patch_general_key(monkeypatch, "contributor_password", "y")

    with client.session_transaction() as sess:
        sess["access_role"] = "admin"
        sess["settings_unlocked"] = True

    assert client.post("/api/ui/settings/logout").status_code == 200
    r = client.get("/api/ui/settings/check-access")
    assert r.status_code == 200
    assert r.get_json().get("unlocked") is False


def test_settings_patch_general_with_admin_session(app, client, monkeypatch):
    """PATCH /api/ui/settings успешно мержит безопасное поле (admin в сессии)."""
    from app_config.app_config import app_config

    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    _patch_general_key(monkeypatch, "settings_password", "patch-admin-pw")
    _patch_general_key(monkeypatch, "contributor_password", "")
    monkeypatch.setattr(app_config, "save", lambda: None)

    token = f"https://patch-{id(app)}.example/feed"
    old_donate = app_config.get("general.donate_url")
    try:
        with client.session_transaction() as sess:
            sess["access_role"] = "admin"

        r = client.patch(
            "/api/ui/settings",
            json={"general": {"donate_url": token}},
            content_type="application/json",
        )
        assert r.status_code == 200
        body = r.get_json() or {}
        assert body.get("general", {}).get("donate_url") == token
        assert app_config.get("general.donate_url") == token
    finally:
        app_config.set("general.donate_url", old_donate)


def test_settings_patch_contributor_merges_safe_field(app, client, monkeypatch):
    """Оператор может PATCH; админские пароли из payload не применяются."""
    from app_config.app_config import app_config

    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    _patch_general_key(monkeypatch, "settings_password", "admin-real")
    _patch_general_key(monkeypatch, "contributor_password", "contrib-real")
    monkeypatch.setattr(app_config, "save", lambda: None)

    token = f"https://contrib-patch-{id(app)}.example/donate"
    old_donate = app_config.get("general.donate_url")
    try:
        with client.session_transaction() as sess:
            sess["access_role"] = "contributor"

        r = client.patch(
            "/api/ui/settings",
            json={
                "general": {
                    "donate_url": token,
                    "settings_password": "should-not-apply",
                    "contributor_password": "also-ignored",
                },
            },
            content_type="application/json",
        )
        assert r.status_code == 200
        assert app_config.get("general.donate_url") == token
        assert app_config.get("general.settings_password") == "admin-real"
        assert app_config.get("general.contributor_password") == "contrib-real"
    finally:
        app_config.set("general.donate_url", old_donate)


def test_settings_patch_contributor_placeholder_does_not_wipe_telegram_token(
    app,
    client,
    monkeypatch,
):
    """*** в PATCH не затирает секрет (как у админа)."""
    from app_config.app_config import app_config

    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    _patch_general_key(monkeypatch, "settings_password", "a")
    _patch_general_key(monkeypatch, "contributor_password", "c")
    monkeypatch.setattr(app_config, "save", lambda: None)

    real = f"tg-token-{id(app)}"
    app_config.config.setdefault("notifications", {})["telegram_bot_token"] = real
    try:
        with client.session_transaction() as sess:
            sess["access_role"] = "contributor"

        r = client.patch(
            "/api/ui/settings",
            json={"notifications": {"telegram_bot_token": "***"}},
            content_type="application/json",
        )
        assert r.status_code == 200
        assert app_config.get("notifications.telegram_bot_token") == real
    finally:
        (app_config.config.get("notifications") or {}).pop("telegram_bot_token", None)
