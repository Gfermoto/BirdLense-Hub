"""Web Push notifications — отправка push в браузер при детекциях."""
import json
import logging
from typing import Literal, Optional

from app_config.app_config import app_config
from models import db, PushSubscription

logger = logging.getLogger(__name__)


def _is_unrecoverable_subscription_error(exc: BaseException) -> bool:
    """Ошибки pywebpush/cryptography при битых p256dh/auth — подписку лучше удалить из БД."""
    msg = str(exc).lower()
    markers = (
        'deserialize',
        'asn.1',
        'invalid length',
        'incorrect format',
        'unsupported key',
        'padding',
        'non-hexadecimal',
        'invalid base64',
        'malformed',
    )
    return any(m in msg for m in markers)


def _ensure_vapid_keys() -> tuple[str, str]:
    """Генерирует и сохраняет VAPID ключи, если их нет.
    pub = base64url для PushManager.subscribe(applicationServerKey)
    priv = PEM строка для pywebpush
    """
    pub = (app_config.get('web_push.vapid_public_key') or '').strip()
    priv = (app_config.get('web_push.vapid_private_key') or '').strip()
    if pub and priv:
        return pub, priv
    try:
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid
        from py_vapid.utils import b64urlencode

        vapid = Vapid()
        vapid.generate_keys()
        raw_pub = vapid.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        pub = b64urlencode(raw_pub)
        priv = vapid.private_pem().decode('utf-8')
        app_config.set('web_push.vapid_public_key', pub)
        app_config.set('web_push.vapid_private_key', priv)
        app_config.save()
        return pub, priv
    except Exception as e:
        logger.warning("Web Push: failed to generate VAPID keys: %s", e)
        raise


def get_vapid_public_key() -> Optional[str]:
    """Возвращает публичный VAPID ключ для подписки клиента.
    Не проверяет enable_notifications — subscribe endpoint это сделает.
    Так пользователь получает понятную ошибку «Notifications disabled» при subscribe,
    а не «Web Push not available» при запросе ключа.
    """
    try:
        pub, _ = _ensure_vapid_keys()
        return pub
    except ImportError as e:
        logger.warning("Web Push: py-vapid not installed: %s", e)
        return None
    except Exception as e:
        logger.warning("Web Push: failed to get VAPID key: %s", e)
        return None


def send_web_push(message: str, link: str = "live", tag: Optional[str] = None) -> int:
    """
    Отправляет push всем подписчикам. Возвращает количество успешно отправленных.
    """
    if not app_config.get('general.enable_notifications'):
        return 0
    if not app_config.get('web_push.enabled', False):
        return 0
    subs = PushSubscription.query.all()
    if not subs:
        return 0
    try:
        pub, priv = _ensure_vapid_keys()
    except Exception:
        return 0
    base_url = (app_config.get('notifications.base_url') or '').strip().rstrip('/')
    url = f"{base_url}/{link}" if base_url else None
    payload = {
        'title': 'BirdLense',
        'body': message,
        'tag': tag or 'detection',
        'url': url or '/',
    }
    payload_json = json.dumps(payload)
    sent = 0
    to_remove: list[int] = []
    try:
        from pywebpush import webpush, WebPushException
        for sub in subs:
            if not (sub.p256dh and sub.auth and sub.endpoint):
                to_remove.append(sub.id)
                logger.info(
                    "Web Push: removing subscription id=%s (missing endpoint or keys)",
                    sub.id,
                )
                continue
            try:
                subscription_info = {
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                }
                webpush(
                    subscription_info=subscription_info,
                    data=payload_json,
                    vapid_private_key=priv,
                    vapid_claims={'sub': 'mailto:birdlense@local'},
                )
                sent += 1
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    to_remove.append(sub.id)
                elif _is_unrecoverable_subscription_error(e):
                    to_remove.append(sub.id)
                    logger.info(
                        "Web Push: removing subscription id=%s (unrecoverable): %s",
                        sub.id,
                        e,
                    )
                else:
                    logger.warning("Web Push failed for %s: %s", sub.endpoint[:50], e)
            except Exception as e:
                if _is_unrecoverable_subscription_error(e):
                    to_remove.append(sub.id)
                    logger.info(
                        "Web Push: removing invalid subscription id=%s: %s",
                        sub.id,
                        e,
                    )
                else:
                    logger.warning("Web Push error for subscription: %s", e)
    except ImportError:
        logger.warning("pywebpush not installed, skipping Web Push")
        return 0
    for sub_id in to_remove:
        PushSubscription.query.filter_by(id=sub_id).delete()
    if to_remove:
        db.session.commit()
    return sent


class PushSubscriptionBodyError(ValueError):
    """Некорректное тело POST /api/ui/push/subscribe."""


def parse_push_subscription_body(data) -> tuple[str, str, str]:
    """endpoint, p256dh, auth."""
    if not isinstance(data, dict):
        data = {}
    sub = data.get('subscription')
    if not sub or not isinstance(sub, dict):
        raise PushSubscriptionBodyError('subscription required')
    endpoint = (sub.get('endpoint') or '').strip()
    keys = sub.get('keys') or {}
    p256dh = (keys.get('p256dh') or '').strip()
    auth = (keys.get('auth') or '').strip()
    if not endpoint or not p256dh or not auth:
        raise PushSubscriptionBodyError(
            'subscription.endpoint and subscription.keys (p256dh, auth) required',
        )
    return endpoint, p256dh, auth


def enable_web_push_and_save() -> None:
    app_config.set('web_push.enabled', True)
    app_config.save()


def upsert_push_subscription(
    session,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str,
) -> Literal['updated', 'created']:
    existing = (
        session.query(PushSubscription).filter_by(endpoint=endpoint).first()
    )
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = user_agent[:512]
        session.commit()
        return 'updated'
    ps = PushSubscription(
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=user_agent[:512],
    )
    session.add(ps)
    session.commit()
    return 'created'
