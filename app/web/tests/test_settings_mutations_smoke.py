"""Smoke tests for settings-gated POST/PATCH (issue #202)."""


def _patch_general_key(monkeypatch, key: str, value):
    """Patch a key inside merged ``general`` (user_config may set passwords)."""
    from app_config.app_config import app_config

    gen = app_config.config.setdefault('general', {})
    monkeypatch.setitem(gen, key, value)


def _open_settings_access(monkeypatch):
    """Empty passwords allow access only outside production (see ``auth.settings_check_access``)."""
    monkeypatch.delenv('BIRDLENSE_ENV', raising=False)
    monkeypatch.delenv('FLASK_ENV', raising=False)
    _patch_general_key(monkeypatch, 'settings_password', '')
    _patch_general_key(monkeypatch, 'contributor_password', '')


def test_birdfood_post_forbidden_when_settings_locked(client, monkeypatch):
    _patch_general_key(monkeypatch, 'settings_password', 'integration-test-lock')
    _patch_general_key(monkeypatch, 'contributor_password', '')

    r = client.post(
        '/api/ui/birdfood',
        json={'name': 'Should Not Be Created'},
        content_type='application/json',
    )
    assert r.status_code == 403


def test_birdfood_post_and_toggle_happy_path(app, client, monkeypatch):
    _open_settings_access(monkeypatch)
    unique = f'CI Birdfood {id(app)}'

    r = client.post(
        '/api/ui/birdfood',
        json={'name': unique, 'active': True},
        content_type='application/json',
    )
    assert r.status_code == 201

    lst = client.get('/api/ui/birdfood').get_json()
    assert isinstance(lst, list)
    row = next((x for x in lst if x['name'] == unique), None)
    assert row is not None
    assert row['active'] is True
    bid = row['id']

    r2 = client.patch(f'/api/ui/birdfood/{bid}/toggle')
    assert r2.status_code == 200

    lst2 = client.get('/api/ui/birdfood').get_json()
    row2 = next(x for x in lst2 if x['id'] == bid)
    assert row2['active'] is False

    with app.app_context():
        from models import BirdFood, db

        db.session.delete(db.session.get(BirdFood, bid))
        db.session.commit()


def test_birdfood_post_duplicate_name_400(app, client, monkeypatch):
    _open_settings_access(monkeypatch)
    unique = f'Dup Birdfood {id(app)}'

    assert client.post(
        '/api/ui/birdfood',
        json={'name': unique},
        content_type='application/json',
    ).status_code == 201

    r = client.post(
        '/api/ui/birdfood',
        json={'name': unique},
        content_type='application/json',
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
    _patch_general_key(monkeypatch, 'enable_notifications', True)
    monkeypatch.setattr(app_config, 'save', lambda: None)

    ep = f'https://example.test/push/ep-{id(app)}'
    r = client.post(
        '/api/ui/push/subscribe',
        json={
            'subscription': {
                'endpoint': ep,
                'keys': {'p256dh': 'k' * 8, 'auth': 'a' * 8},
            },
        },
        content_type='application/json',
    )
    assert r.status_code in (200, 201)

    with app.app_context():
        from models import PushSubscription, db

        row = PushSubscription.query.filter_by(endpoint=ep).first()
        assert row is not None
        db.session.delete(row)
        db.session.commit()
