"""Telegram and Web Push notification helpers.

Extracted from util.py. util.py re-exports everything here for backward compatibility.

Note: path-safety helpers (`read_safe_image_bytes`, `remove_safe_image_file`) are lazy-imported
from util where needed to avoid a circular import at module load time (util imports this module).
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

import requests

from app_config.app_config import app_config


def _telegram_button_open_live(link, emoji='▶', style='primary', icon_custom_emoji_id=None):
    """Inline button 'Open' with emoji and style (Bot API 9.4+).
    icon_custom_emoji_id: optional, для Premium — кастомный эмодзи вместо Unicode.
    """
    label = 'Open video' if '/videos/' in (link or '') else 'Open live'
    btn = {'text': label, 'url': link, 'style': style}
    if icon_custom_emoji_id:
        btn['icon_custom_emoji_id'] = icon_custom_emoji_id
    else:
        btn['text'] = f'{emoji} {label}'
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


def _telegram_proxy_mode():
    """none | socks_http | mtproto — см. notifications.telegram_proxy_type."""
    from telegram_mtproto import telegram_proxy_type

    return telegram_proxy_type()


def _telegram_http_proxies():
    """Прокси для исходящих запросов к Telegram (SOCKS5h, HTTP). Пусто — без прокси."""
    if _telegram_proxy_mode() != 'socks_http':
        return None
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


def _compress_image_for_telegram(image_bytes, aggressive=False):
    """Сжать и/или уменьшить JPEG для Telegram. В уведомлениях уже шлём кропы (bounding box) с процессора."""
    max_side = int(app_config.get('notifications.telegram_max_side_px') or 0)
    limit_kb = int(app_config.get('notifications.compress_photo_over_kb') or 0)
    if aggressive:
        max_side = min(max_side or 1280, 1280)
        limit_kb = min(limit_kb or 512, 512)
    # Даже без явного resize/compress нормализуем слишком маленькие/битые превью:
    # Telegram иногда отвечает IMAGE_PROCESS_FAILED на экзотичных кропах.
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        w, h = img.size
        # Слишком маленькие кропы Telegram может отвергать; поднимаем минимум.
        if min(w, h) < 64:
            ratio = 64 / float(min(w, h))
            new_size = (max(64, int(w * ratio)), max(64, int(h * ratio)))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            w, h = img.size
        if max_side > 0 and max(w, h) > max_side:
            ratio = max_side / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logging.debug("Telegram: resized to %s (max_side=%s)", new_size, max_side)
        buf = io.BytesIO()
        quality = 72 if aggressive else 85
        img.save(buf, 'JPEG', quality=quality, optimize=True)
        out = buf.getvalue()
        if limit_kb > 0 and len(out) > limit_kb * 1024:
            buf2 = io.BytesIO()
            img.save(buf2, 'JPEG', quality=68 if aggressive else 78, optimize=True)
            out = buf2.getvalue()
        if len(out) < len(image_bytes):
            logging.debug("Telegram: %d -> %d bytes", len(image_bytes), len(out))
        return out
    except Exception as e:
        logging.debug("Telegram image process (PIL) failed: %s", e)
    # Fallback для окружений без Pillow или при битом EXIF: пробуем OpenCV decode/encode.
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        h, w = img.shape[:2]
        if min(h, w) < 64:
            ratio = 64.0 / float(min(h, w))
            img = cv2.resize(img, (max(64, int(w * ratio)), max(64, int(h * ratio))), interpolation=cv2.INTER_CUBIC)
            h, w = img.shape[:2]
        if max_side > 0 and max(w, h) > max_side:
            ratio = max_side / float(max(w, h))
            img = cv2.resize(img, (max(1, int(w * ratio)), max(1, int(h * ratio))), interpolation=cv2.INTER_AREA)
        ok, enc = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 72 if aggressive else 85])
        if not ok:
            return image_bytes
        out = enc.tobytes()
        if limit_kb > 0 and len(out) > limit_kb * 1024:
            ok2, enc2 = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 68 if aggressive else 78])
            if ok2:
                out = enc2.tobytes()
        return out
    except Exception as e:
        logging.debug("Telegram image process (cv2) failed: %s", e)
    return image_bytes


def _telegram_message_thread_id_int():
    thread_id = app_config.get('notifications.message_thread_id')
    if thread_id is None or thread_id == '':
        return None
    try:
        return int(thread_id)
    except (ValueError, TypeError):
        return None


def _telegram_fallback_note(reason):
    notes = {
        'no_preview': 'photo unavailable: no preview generated',
        'decode_failed': 'photo unavailable: preview decode failed',
        'telegram_photo_failed': 'photo unavailable: Telegram rejected media',
        'config_disabled': 'photo unavailable: photo sending disabled',
        'unsafe_path': 'photo unavailable: unsafe file path',
        'read_failed': 'photo unavailable: preview file read failed',
    }
    note = notes.get(reason)
    if not note:
        return ''
    return f'\n\n<i>{note}</i>'


def _telegram_send_message(token, chat_id, text, link=None, button_emoji='📺',
                           button_style='primary', button_tags=None, **kwargs):
    """Build and send Telegram message with HTML, keyboard, options."""
    if _telegram_proxy_mode() == 'mtproto':
        from telegram_mtproto import mtproto_send

        timeout_text, _ = _telegram_timeouts()
        retries = int(app_config.get('notifications.telegram_retries') or 3)
        retries = max(1, min(5, retries))
        return mtproto_send(
            token=token,
            chat_id=str(chat_id),
            text=text,
            link_url=link,
            button_emoji=button_emoji,
            image_bytes=None,
            caption='',
            disable_notification=app_config.get('notifications.disable_notification', False),
            link_preview_large=bool(app_config.get('notifications.link_preview_large', False)),
            message_thread_id=_telegram_message_thread_id_int(),
            timeout_sec=timeout_text,
            request_retries=retries,
        )

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
    tid = _telegram_message_thread_id_int()
    if tid is not None:
        payload['message_thread_id'] = tid
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
    except Exception as e:
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
    if (_os.environ.get('BIRDLENSE_NOTIFY_APP_STARTUP') or '1').strip().lower() in (
        '0', 'false', 'no',
    ):
        logging.info('notify_app_startup: skip (BIRDLENSE_NOTIFY_APP_STARTUP disabled)')
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
                notify(
                    "App is UP!",
                    link=None,
                    tags="rocket",
                    timestamp=datetime.now(timezone.utc),
                    send_photo_override=False,
                )
        else:
            notify(
                "App is UP!",
                link=None,
                tags="rocket",
                timestamp=datetime.now(timezone.utc),
                send_photo_override=False,
            )
    except Exception as e:
        logging.warning("notify_app_startup failed: %s", e)


def notify(
    message,
    link='live',
    tags=None,
    image_path=None,
    image_bytes=None,
    timestamp=None,
    fallback_reason_hint=None,
    send_photo_override=None,
):
    """Send notification via Telegram and/or Web Push. Requires token+chat_id or Web Push subscribers.

    image_path: path to image file (must pass _is_safe_image_path when used).
    image_bytes: raw JPEG bytes (alternative to image_path, preferred when processor sends base64).
    timestamp: datetime or Unix int for dynamic time <t:unix:R> (Bot API 9.5).
    """
    result = {
        'telegram_delivery': 'skipped',
        'photo_requested': False,
        'photo_available': False,
        'photo_sent': False,
        'fallback_reason': None,
        'link_url': None,
    }
    if not app_config.get('general.enable_notifications'):
        result['fallback_reason'] = 'notifications_disabled'
        return result
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
        result['fallback_reason'] = 'telegram_not_configured'
        return result
    base_url = (app_config.get('notifications.base_url') or '').strip().rstrip('/')
    if isinstance(link, str) and (link.startswith('http://') or link.startswith('https://')):
        link_url = link
    else:
        link_url = f"{base_url}/{str(link).lstrip('/')}" if base_url and link else None
    result['link_url'] = link_url
    text = message
    button_emoji = '▶'
    button_tags = tags
    # Less visual noise in messages: no leading species emoji in caption/text.
    if tags == 'rocket':
        text = f"🚀 {message}"
    if timestamp is not None:
        unix_ts = int(timestamp.timestamp()) if hasattr(timestamp, 'timestamp') else int(timestamp)
        # Bot API 9.5: <tg-time> — динамическое время в часовом поясе подписчика
        text = f'{text} <tg-time unix="{unix_ts}" format="r">just now</tg-time>'
    try:
        send_photo = app_config.get('notifications.send_photo', True)
        if send_photo_override is not None:
            send_photo = bool(send_photo_override)
        intentional_text_only = send_photo_override is False
        result['photo_requested'] = bool(send_photo)
        # Prefer image_bytes (from processor base64) — не зависит от общего файлового пространства
        image_to_send = None
        image_issue = None
        if send_photo and image_bytes and isinstance(image_bytes, bytes) and len(image_bytes) > 0:
            image_to_send = image_bytes
        elif send_photo and image_path:
            # Lazy import to avoid circular dependency (util imports from notifications)
            from util import read_safe_image_bytes

            image_to_send, io_err = read_safe_image_bytes(image_path)
            if io_err:
                image_to_send = None
                image_issue = io_err
        elif not send_photo:
            image_issue = None if intentional_text_only else 'config_disabled'
        else:
            image_issue = 'no_preview'
        result['photo_available'] = bool(image_to_send)
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

            _, timeout_media = _telegram_timeouts()
            logging.info(
                "Telegram: sending photo (%d bytes), timeout=%ds",
                len(image_to_send),
                timeout_media,
            )
            photo_failed = False
            r = None
            photo_failure_text = None
            aggressive_photo = None

            if _telegram_proxy_mode() == 'mtproto':
                from telegram_mtproto import mtproto_send

                if view_stars > 0:
                    logging.warning(
                        "Telegram MTProto: paid media (Stars) через Telethon не поддерживается — обычное фото",
                    )
                retries = int(app_config.get('notifications.telegram_retries') or 3)
                retries = max(1, min(5, retries))
                r = mtproto_send(
                    token=token,
                    chat_id=str(chat_id),
                    text=text,
                    link_url=link_url,
                    button_emoji=button_emoji,
                    image_bytes=image_to_send,
                    caption=caption,
                    disable_notification=app_config.get(
                        'notifications.disable_notification', False),
                    link_preview_large=bool(app_config.get(
                        'notifications.link_preview_large', False)),
                    message_thread_id=_telegram_message_thread_id_int(),
                    timeout_sec=timeout_media,
                    request_retries=retries,
                )
                photo_failed = not r.ok
            else:
                def _bot_api_send_photo(photo_bytes):
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
                    tid = _telegram_message_thread_id_int()
                    if tid is not None:
                        payload['message_thread_id'] = tid
                    if link_url:
                        custom_id = _get_button_custom_emoji_id(button_tags)
                        payload['reply_markup'] = {
                            'inline_keyboard': [[_telegram_button_open_live(
                                link_url, button_emoji, 'primary',
                                icon_custom_emoji_id=custom_id)]]
                        }

                    base = _get_telegram_api_base()
                    data = _payload_for_telegram_multipart(payload)
                    if view_stars > 0:
                        data['star_count'] = view_stars
                        data['media'] = json.dumps([
                            {'type': 'photo', 'media': 'attach://photo'}
                        ])
                        return _telegram_request(
                            'POST', f"{base}/bot{token}/sendPaidMedia",
                            timeout=timeout_media,
                            data=data,
                            files={'photo': ('photo.jpg', photo_bytes, 'image/jpeg')},
                        )
                    return _telegram_request(
                        'POST', f"{base}/bot{token}/sendPhoto",
                        timeout=timeout_media,
                        data=data,
                        files={'photo': ('photo.jpg', photo_bytes, 'image/jpeg')},
                    )

                try:
                    r = _bot_api_send_photo(image_to_send)
                except (requests.Timeout, requests.ConnectionError, OSError) as e:
                    logging.warning(
                        "Telegram photo failed (timeout/network): %s — fallback to text",
                        e,
                    )
                    photo_failed = True
                    photo_failure_text = str(e)
            if r is not None and not r.ok:
                logging.warning(
                    "Telegram sendPhoto HTTP %s: %s",
                    r.status_code,
                    (r.text or "")[:500],
                )
                photo_failed = True
                photo_failure_text = (r.text or "")[:500]
            if (
                photo_failed
                and _telegram_proxy_mode() != 'mtproto'
                and photo_failure_text
                and 'IMAGE_PROCESS_FAILED' in photo_failure_text
            ):
                aggressive_photo = _compress_image_for_telegram(image_to_send, aggressive=True)
                if aggressive_photo and aggressive_photo != image_to_send:
                    logging.warning("Telegram: retrying photo with aggressive JPEG normalization")
                    try:
                        r = _bot_api_send_photo(aggressive_photo)
                        if r is not None and r.ok:
                            photo_failed = False
                            photo_failure_text = None
                        elif r is not None:
                            photo_failure_text = (r.text or "")[:500]
                    except (requests.Timeout, requests.ConnectionError, OSError) as e:
                        photo_failure_text = str(e)
            if photo_failed:
                result['fallback_reason'] = 'telegram_photo_failed'
                fallback_text = f'{text}{_telegram_fallback_note(result["fallback_reason"])}'
                try:
                    r = _telegram_send_message(
                        token, chat_id, fallback_text, link=link_url,
                        button_emoji=button_emoji, button_style='primary',
                        button_tags=button_tags)
                    result['telegram_delivery'] = 'text_fallback'
                except requests.RequestException as fallback_e:
                    logging.warning("Telegram text fallback also failed: %s", fallback_e)
                    r = None
                    result['telegram_delivery'] = 'failed'
                    result['fallback_reason'] = 'telegram_text_failed'
            else:
                result['telegram_delivery'] = 'photo'
                result['photo_sent'] = True
            if r is None:
                result['fallback_reason'] = result['fallback_reason'] or 'telegram_text_failed'
                return result
            # Lazy import to avoid circular dependency
            from util import remove_safe_image_file

            remove_safe_image_file(image_path)
        else:
            if result['fallback_reason'] is None and not intentional_text_only:
                result['fallback_reason'] = fallback_reason_hint or image_issue or 'no_preview'
            fallback_text = text
            if result['fallback_reason']:
                fallback_text = f'{text}{_telegram_fallback_note(result["fallback_reason"])}'
            r = _telegram_send_message(
                token, chat_id, fallback_text, link=link_url,
                button_emoji=button_emoji, button_style='primary',
                button_tags=button_tags)
            result['telegram_delivery'] = 'text'
        if r is not None and not r.ok:
            logging.warning(
                "Telegram notify failed: %s %s",
                r.status_code,
                (getattr(r, "text", "") or "")[:300],
            )
            result['telegram_delivery'] = 'failed'
            result['fallback_reason'] = result['fallback_reason'] or 'telegram_text_failed'
    except Exception as e:
        logging.warning("Telegram notify error: %s", e)
        result['telegram_delivery'] = 'failed'
        result['fallback_reason'] = result['fallback_reason'] or 'unexpected_error'
    return result
