"""Web Push: очистка битых подписок при отправке."""
import pytest


class TestSendWebPushCleanup:
    """send_web_push удаляет нечитаемые подписки из БД."""

    def test_drops_sub_on_key_deserialize_error(self, app, monkeypatch):
        """Ошибка десериализации ключей → запись PushSubscription удалена."""
        import pywebpush

        from app_config.app_config import app_config
        from models import PushSubscription, db
        from services.web_push_service import send_web_push

        with app.app_context():
            app_config.set('general.enable_notifications', True)
            app_config.set('web_push.enabled', True)
            ps = PushSubscription(
                endpoint='https://push.example.invalid/endpoint',
                p256dh='corrupt-p256dh',
                auth='corrupt-auth',
            )
            db.session.add(ps)
            db.session.commit()
            sub_id = ps.id

            def fake_webpush(*_args, **_kwargs):
                raise ValueError(
                    'Could not deserialize key data. '
                    'ASN.1 parsing error: invalid length'
                )

            monkeypatch.setattr(pywebpush, 'webpush', fake_webpush)
            sent = send_web_push('test message')
            assert sent == 0
            assert PushSubscription.query.filter_by(id=sub_id).first() is None

    def test_removes_subscription_missing_keys(self, app, monkeypatch):
        """Пустой p256dh — без вызова webpush, подписка удалена."""
        import pywebpush

        from app_config.app_config import app_config
        from models import PushSubscription, db
        from services.web_push_service import send_web_push

        with app.app_context():
            app_config.set('general.enable_notifications', True)
            app_config.set('web_push.enabled', True)
            ps = PushSubscription(
                endpoint='https://push.example.invalid/e2',
                p256dh='',
                auth='x',
            )
            db.session.add(ps)
            db.session.commit()
            sub_id = ps.id

            def should_not_call(*_a, **_k):
                pytest.fail('webpush should not run for empty p256dh')

            monkeypatch.setattr(pywebpush, 'webpush', should_not_call)
            sent = send_web_push('x')
            assert sent == 0
            assert PushSubscription.query.filter_by(id=sub_id).first() is None
