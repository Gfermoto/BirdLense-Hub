"""Telegram and Web Push notification helpers.

Extracted from util.py. util.py re-exports everything here for backward compatibility.

Note: notify() and notify_app_startup() use lazy imports from util for path-safety helpers
(_safe_image_path_or_none, _data_dir) to avoid a circular import at module load time.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

import requests

from app_config.app_config import app_config


def _telegram_button_open_live(link, emoji='📺', style='primary', icon_custom_emoji_id=None):
    """Inline button 'Open Live' with emoji and style (Bot API 9.4+).
    icon_custom_emoji_id: optional, для Premium — кастомный эмодзи вместо Unicode.
    """
    btn = {'text': 'Open Live', 'url': link, 'style': style}
    if icon_custom_emoji_id:
        btn['icon_custom_emoji_id'] = icon_custom_emoji_id
    else:
        btn['text'] = f'{emoji} Open Live'
    return btn


def _get_button_custom_emoji_id(tags):
    """Возвращает icon_custom_emoji_id для кнопки, если use_custom_emoji и ID задан."""
    if not app_config.get('notifications.use_custom_emoji', False):
        return None
    key = 'custom_emoji_id_chipmunk' if tags == 'chipmunk' else (
        'custom_emoji_id_bird' if tags == 'bird' else 'custom_emoji_id_open_live'
    )
    val = (app_config.get(f'notifications.{key}') or '').strip()
    return val if val else None


def _get_telegram_api_base():
    """Base URL для Telegram Bot API. Прокси/альтернатива при троттлинге."""
    base = (app_config.get('notifications.telegram_api_base') or '').strip().rstrip('/')
    return base or 'https://api.telegram.org'


def _telegram_http_proxies():
    """Прокси для исходящих запросов к Telegram (SOCKS5h, HTTP). Пусто — без прокси."""
    url = (app_config.get('notifications.telegram_proxy_url') or '').strip()
    if not url:
        return None
    return {'http': url, 'https': url}


def _telegram_timeouts():
    """(timeout_text, timeout_media) — текст легче, медиа тяжелее. В РФ таймауты большие (блокировки)."""
    t = int(app_config.get('notifications.telegram_timeout') or 300)
    t = max(30, min(600, t))  # до 10 мин при блокировках
    return t // 2, t


def _telegram_request(method, url, timeout, retries=None, **kwargs):
    """Запрос к Telegram API с повторами при таймауте/сетевой ошибке."""
    retries = retries or int(app_config.get('notifications.telegram_retries') or 3)
    retries = max(1, min(5, retries))
    last_exc = None
    proxies = _telegram_http_proxies()
    if proxies and 'proxies' not in kwargs:
        kwargs = {**kwargs, 'proxies': proxies}
    for attempt in range(retries):
        try:
            r = requests.request(method, url, timeout=timeout, **kwargs)
            return r
        except (requests.Timeout, requests.ConnectionError, OSError) as e:
            last_exc = e
            if attempt < retries - 1:
                delay = 2 ** attempt
                logging.warning(
                    "Telegram attempt %d/%d failed (%s), retry in %ds",
                    attempt + 1, retries, type(e).__name__, delay)
                time.sleep(delay)
    raise last_exc


def _payload_for_telegram_multipart(payload):
    """Для multipart/form-data Telegram ожидает булевы как строки 'true'/'false'."""
    out = {}
    for k, v in payload.items():
        if isinstance(v, bool):
            out[k] = 'true' if v else 'false'
        elif isinstance(v, dict):
            out[k] = json.dumps(v)
        else:
            out[k] = v
    return out


def _compress_image_for_telegram(image_bytes):
    """Сжать и/или уменьшить JPEG для Telegram. В уведомлениях уже шлём кропы (bounding box) с процессора."""
    max_side = int(app_config.get('notifications.telegram_max_side_px') or 0)
    limit_kb = int(app_config.get('notifications.compress_photo_over_kb') or 0)
    if max_side <= 0 and (limit_kb <= 0 or len(image_bytes) <= limit_kb * 1024):
        return image_bytes
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        w, h = img.size
        if max_side > 0 and max(w, h) > max_side:
            ratio = max_side / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logging.debug("Telegram: resized to %s (max_side=%s)", new_size, max_side)
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=85, optimize=True)
        out = buf.getvalue()
        if limit_kb > 0 and len(out) > limit_kb * 1024:
            buf2 = io.BytesIO()
            img.save(buf2, 'JPEG', quality=78, optimize=True)
            out = buf2.getvalue()
        if len(out) < len(image_bytes):
            logging.debug("Telegram: %d -> %d bytes", len(image_bytes), len(out))
        return out
    except Exception as e:
        logging.debug("Telegram image process skip: %s", e)
    return image_bytes


def _telegram_send_message(token, chat_id, text, link=None, button_emoji='📺',
                           button_style='primary', button_tags=None, **kwargs):
    """Build and send Telegram message with HTML, keyboard, options."""
    link_preview = {'is_disabled': True}
    if link and app_config.get('notifications.link_preview_large', False):
        link_preview = {'is_disabled': False, 'prefer_large_media': True}
        text = f"{text}\n\n{link}"

    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_notification': app_config.get(
            'notifications.disable_notification', False),
        'protect_content': app_config.get(
            'notifications.protect_content', False),
        'link_preview_options': link_preview,
    }
    thread_id = app_config.get('notifications.message_thread_id')
    if thread_id is not None and thread_id != '':
        try:
            payload['message_thread_id'] = int(thread_id)
        except (ValueError, TypeError):
            pass
    if link:
        custom_id = _get_button_custom_emoji_id(button_tags)
        payload['reply_markup'] = {
            'inline_keyboard': [[_telegram_button_open_live(
                link, button_emoji, button_style, icon_custom_emoji_id=custom_id)]]
        }
    payload.update(kwargs)
    base = _get_telegram_api_base()
    timeout_text, _ = _telegram_timeouts()
    url = f"{base}/bot{token}/sendMessage"
    return _telegram_request('POST', url, timeout=timeout_text, json=payload)


def notify_telegram_test(message="Test notification from BirdLense"):
    """Отправить тестовое сообщение в Telegram. Возвращает (success, error_message)."""
    if not app_config.get('general.enable_notifications'):
        return False, 'Notifications disabled'
    token = (app_config.get('notifications.telegram_bot_token') or '').strip()
    chat_id = (app_config.get('notifications.telegram_chat_id') or '').strip()
    if not token or not chat_id:
        return False, 'Telegram bot token or chat_id not configured'
    text = f"🚀 {message}"
    try:
        r = _telegram_send_message(token, chat_id, text, link=None)
        if r.ok:
            return True, None
        err = r.json() if r.text else {}
        desc = err.get('description', r.text[:200] if r.text else str(r.status_code))
        return False, desc
    except requests.RequestException as e:
        return False, str(e)


def notify_app_startup(app=None):
    """Send 'App is UP!' on startup. Skips when TESTING (pytest creates app 45×).
    Skips when startup is due to 'restart processor' from UI (marker file .startup_notify_skip
    in data_dir with recent mtime). Skips when already sent in this container run (marker in
    /tmp — survives worker restarts but not container restart) to avoid TG spam.
    Marker is created BEFORE notify() so that if we crash during send, we don't send again."""
    import os as _os
    if _os.environ.get('FLASK_TESTING') or (app and app.config.get('TESTING')):
        return
    sent_marker = '/tmp/.birdlense_startup_notify_sent'  # not in volume → one send per container
    try:
        if os.path.exists(sent_marker):
            logging.info(
                "notify_app_startup: skip (marker exists, pid=%s)",
                os.getpid(),
            )
            return  # already sent this container run (e.g. after gunicorn worker restart)
        # Lazy import to avoid circular dependency (util imports from notifications)
        from util import _data_dir
        skip_marker = os.path.join(_data_dir(), '.startup_notify_skip')
        if os.path.exists(skip_marker):
            age_sec = time.time() - os.path.getmtime(skip_marker)
            if age_sec <= 120:
                try:
                    os.remove(skip_marker)
                except OSError:
                    pass
                logging.info("notify_app_startup: skip (restart processor, pid=%s)", os.getpid())
                return  # restart was from UI "restart processor", skip TG
            try:
                os.remove(skip_marker)
            except OSError:
                pass
        # Create marker BEFORE notify so crash during send doesn't cause resend on next start
        try:
            open(sent_marker, 'a').close()
        except OSError:
            pass
        logging.info("notify_app_startup: sending (pid=%s)", os.getpid())
        # Web Push / DB (PushSubscription) need Flask application context
        if app is not None:
            with app.app_context():
                notify("App is UP!", tags="rocket", timestamp=datetime.now(timezone.utc))
        else:
            notify("App is UP!", tags="rocket", timestamp=datetime.now(timezone.utc))
    except Exception as e:
        logging.warning("notify_app_startup failed: %s", e)


def notify(message, link="live", tags=None, image_path=None, image_bytes=None, timestamp=None):
    """Send notification via Telegram and/or Web Push. Requires token+chat_id or Web Push subscribers.

    image_path: path to image file (must pass _is_safe_image_path when used).
    image_bytes: raw JPEG bytes (alternative to image_path, preferred when processor sends base64).
    timestamp: datetime or Unix int for dynamic time <t:unix:R> (Bot API 9.5).
    """
    if not app_config.get('general.enable_notifications'):
        return
    # Web Push (параллельно с Telegram)
    try:
        from services.web_push_service import send_web_push
        icon = "chipmunk" if tags and any(s in (tags or "").lower() for s in (
            "squirrel", "chipmunk", "mouse", "мышь", "белка")) else "bird"
        send_web_push(message, link=link, tag=icon)
    except Exception as e:
        logging.warning("Web Push notify error: %s", e)
    token = (app_config.get('notifications.telegram_bot_token') or '').strip()
    chat_id = (app_config.get('notifications.telegram_chat_id') or '').strip()
    if not token or not chat_id:
        return
    base_url = (app_config.get('notifications.base_url') or '').strip().rstrip('/')
    link_url = f"{base_url}/{link}" if base_url else None
    text = message
    button_emoji = '📺'
    button_tags = tags
    if tags:
        emoji = {'chipmunk': '🐿️', 'bird': '🐦', 'rocket': '🚀'}.get(tags, '🐦')
        text = f"{emoji} {message}"
        button_emoji = emoji if tags in ('chipmunk', 'bird') else '📺'
    if timestamp is not None:
        unix_ts = int(timestamp.timestamp()) if hasattr(timestamp, 'timestamp') else int(timestamp)
        # Bot API 9.5: <tg-time> — динамическое время в часовом поясе подписчика
        text = f'{text} <tg-time unix="{unix_ts}" format="r">just now</tg-time>'
    try:
        send_photo = app_config.get('notifications.send_photo', True)
        # Prefer image_bytes (from processor base64) — не зависит от общего файлового пространства
        image_to_send = None
        if send_photo and image_bytes and isinstance(image_bytes, bytes) and len(image_bytes) > 0:
            image_to_send = image_bytes
        elif send_photo and image_path:
            # Lazy import to avoid circular dependency (util imports from notifications)
            from util import _safe_image_path_or_none
            safe_img_path = _safe_image_path_or_none(image_path)
            if safe_img_path:
                try:
                    with open(safe_img_path, 'rb') as f:
                        image_to_send = f.read()
                except OSError as e:
                    logging.warning("Cannot read image for Telegram: %s", e)
                    image_to_send = None
        if image_to_send:
            image_to_send = _compress_image_for_telegram(image_to_send)
            view_stars = app_config.get('notifications.paid_media_view_star_count')
            forward_stars = app_config.get('notifications.paid_media_forward_star_count')
            try:
                view_stars = int(view_stars) if view_stars else 0
            except (ValueError, TypeError):
                view_stars = 0
            try:
                forward_stars = int(forward_stars) if forward_stars else 0
            except (ValueError, TypeError):
                forward_stars = 0
            view_stars = max(0, min(25000, view_stars))
            forward_stars = max(0, min(25000, forward_stars))

            # protect_content: при бесплатном просмотре — запретить пересылку, если forward_stars > 0
            # (Telegram не поддерживает отдельную плату за пересылку)
            protect = app_config.get('notifications.protect_content', False)
            if view_stars == 0 and forward_stars > 0:
                protect = True

            caption = text
            if link_url and app_config.get('notifications.link_preview_large', False):
                caption = f"{text}\n\n{link_url}"
            payload = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'HTML',
                'disable_notification': app_config.get(
                    'notifications.disable_notification', False),
                'protect_content': protect,
            }
            if link_url and app_config.get('notifications.link_preview_large', False):
                payload['link_preview_options'] = {'is_disabled': False, 'prefer_large_media': True}
            thread_id = app_config.get('notifications.message_thread_id')
            if thread_id not in (None, ''):
                try:
                    payload['message_thread_id'] = int(thread_id)
                except (ValueError, TypeError):
                    pass
            if link_url:
                custom_id = _get_button_custom_emoji_id(button_tags)
                payload['reply_markup'] = {
                    'inline_keyboard': [[_telegram_button_open_live(
                        link_url, button_emoji, 'primary',
                        icon_custom_emoji_id=custom_id)]]
                }

            base = _get_telegram_api_base()
            _, timeout_media = _telegram_timeouts()
            logging.info(
                "Telegram: sending photo (%d bytes), timeout=%ds",
                len(image_to_send),
                timeout_media,
            )
            photo_failed = False
            r = None
            try:
                data = _payload_for_telegram_multipart(payload)
                if view_stars > 0:
                    data['star_count'] = view_stars
                    data['media'] = json.dumps([
                        {'type': 'photo', 'media': 'attach://photo'}
                    ])
                    r = _telegram_request(
                        'POST', f"{base}/bot{token}/sendPaidMedia",
                        timeout=timeout_media,
                        data=data,
                        files={'photo': ('photo.jpg', image_to_send, 'image/jpeg')},
                    )
                else:
                    r = _telegram_request(
                        'POST', f"{base}/bot{token}/sendPhoto",
                        timeout=timeout_media,
                        data=data,
                        files={'photo': ('photo.jpg', image_to_send, 'image/jpeg')},
                    )
            except (requests.Timeout, requests.ConnectionError, OSError) as e:
                logging.warning(
                    "Telegram photo failed (timeout/network): %s — fallback to text",
                    e,
                )
                photo_failed = True
            if r is not None and not r.ok:
                logging.warning(
                    "Telegram sendPhoto HTTP %s: %s",
                    r.status_code,
                    (r.text or "")[:500],
                )
                photo_failed = True
            if photo_failed:
                try:
                    r = _telegram_send_message(
                        token, chat_id, text, link=link_url,
                        button_emoji=button_emoji, button_style='primary',
                        button_tags=button_tags)
                except requests.RequestException as fallback_e:
                    logging.warning("Telegram text fallback also failed: %s", fallback_e)
                    r = None
            if r is None:
                return
            # Lazy import to avoid circular dependency
            from util import _safe_image_path_or_none
            safe_rm = _safe_image_path_or_none(image_path)
            if safe_rm and os.path.isfile(safe_rm):
                try:
                    os.remove(safe_rm)
                except OSError:
                    pass
        else:
            r = _telegram_send_message(
                token, chat_id, text, link=link_url,
                button_emoji=button_emoji, button_style='primary',
                button_tags=button_tags)
        if r is not None and not r.ok:
            logging.warning(
                "Telegram notify failed: %s %s",
                r.status_code,
                (getattr(r, "text", "") or "")[:300],
            )
    except requests.RequestException as e:
        logging.warning("Telegram notify error: %s", e)
