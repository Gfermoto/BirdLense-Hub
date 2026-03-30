"""
Отправка в Telegram через Telethon при MTProto-прокси (сервер / порт / секрет, как в приложении Telegram).
Bot API по HTTPS через requests с SOCKS/HTTP не использует MTProto — здесь нативный MTProto-туннель.
Требуются api_id и api_hash с https://my.telegram.org (или env TELEGRAM_API_ID / TELEGRAM_API_HASH).
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


def _parse_api_id(val) -> int:
    """Из конфига/YAML api_id может прийти как int, float или строка «12345.0»."""
    if val is None or val == "":
        return 0
    if isinstance(val, bool):
        return 0
    if isinstance(val, int):
        return val if val > 0 else 0
    if isinstance(val, float):
        try:
            i = int(val)
            return i if i > 0 else 0
        except (ValueError, OverflowError):
            return 0
    s = str(val).strip()
    if not s:
        return 0
    try:
        i = int(float(s))
        return i if i > 0 else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def _parse_port(val) -> int:
    if val is None or val == "":
        return 0
    if isinstance(val, (int, float)):
        try:
            p = int(val)
            return p if 1 <= p <= 65535 else 0
        except (ValueError, OverflowError):
            return 0
    try:
        p = int(float(str(val).strip()))
        return p if 1 <= p <= 65535 else 0
    except (ValueError, TypeError, OverflowError):
        return 0


class _TelegramHttpShim:
    """Минимальная совместимость с requests.Response для notify()."""

    __slots__ = ("ok", "status_code", "text")

    def __init__(self, ok: bool, status_code: int = 200, text: str = ""):
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self):
        try:
            import json

            return json.loads(self.text) if self.text else {}
        except Exception:
            return {}


def _telegram_api_credentials():
    """(api_id:int, api_hash:str) или (0, '')."""
    raw_env = (os.environ.get("TELEGRAM_API_ID") or "").strip()
    if raw_env:
        api_id = _parse_api_id(raw_env)
    else:
        from app_config.app_config import app_config

        api_id = _parse_api_id(app_config.get("notifications.telegram_api_id"))
    api_hash = (os.environ.get("TELEGRAM_API_HASH") or "").strip()
    if not api_hash:
        from app_config.app_config import app_config

        api_hash = (app_config.get("notifications.telegram_api_hash") or "").strip()
    return api_id, api_hash


def _mtproxy_connection_class(secret_hex: str):
    s = (secret_hex or "").strip().lower()
    if s.startswith("dd"):
        from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate

        return ConnectionTcpMTProxyRandomizedIntermediate
    from telethon.network.connection import ConnectionTcpMTProxyIntermediate

    return ConnectionTcpMTProxyIntermediate


def _run_coro_sync(coro):
    """Запуск async из sync-кода (Gunicorn sync worker)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    done: list[Any] = []
    err: list[BaseException] = []

    def _worker():
        try:
            done.append(asyncio.run(coro))
        except BaseException as e:
            err.append(e)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=600)
    if t.is_alive():
        raise TimeoutError("Telegram MTProto: timeout waiting for worker thread")
    if err:
        raise err[0]
    return done[0] if done else None


async def _mtproto_send_inner(
    *,
    token: str,
    chat_id: str,
    text: str,
    link_url: Optional[str],
    button_emoji: str,
    image_bytes: Optional[bytes],
    caption: str,
    disable_notification: bool,
    link_preview_large: bool,
    message_thread_id: Optional[int],
    timeout_sec: int,
    request_retries: int,
) -> _TelegramHttpShim:
    from telethon import Button
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from app_config.app_config import app_config

    api_id, api_hash = _telegram_api_credentials()
    if api_id <= 0 or not api_hash:
        return _TelegramHttpShim(
            False,
            400,
            '{"description":"MTProto: задайте notifications.telegram_api_id и telegram_api_hash '
            '(или TELEGRAM_API_ID / TELEGRAM_API_HASH) с https://my.telegram.org"}',
        )

    host = (app_config.get("notifications.telegram_mtproto_host") or "").strip()
    port = _parse_port(app_config.get("notifications.telegram_mtproto_port"))
    secret = (app_config.get("notifications.telegram_mtproto_secret") or "").strip()
    if not host or port <= 0 or not secret:
        return _TelegramHttpShim(
            False,
            400,
            '{"description":"MTProto: задайте сервер, порт и секрет прокси"}',
        )

    conn_cls = _mtproxy_connection_class(secret)
    proxy = (host, port, secret)

    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
        connection=conn_cls,
        proxy=proxy,
        timeout=timeout_sec,
        request_retries=request_retries,
    )

    buttons = None
    if link_url:
        # Telethon Button.url — только текст; кастомные emoji Premium через Bot API отдельно не подключаем
        btn = Button.url(f"{button_emoji} Open Live", link_url)
        buttons = [[btn]]

    try:
        await client.start(bot_token=token)
        entity: Union[int, str] = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id

        link_preview = link_preview_large
        silent = disable_notification
        reply_to = message_thread_id if message_thread_id is not None else None

        if image_bytes:
            await client.send_message(
                entity,
                caption or " ",
                file=image_bytes,
                parse_mode="html",
                buttons=buttons,
                silent=silent,
                link_preview=link_preview,
                reply_to=reply_to,
            )
        else:
            await client.send_message(
                entity,
                text,
                parse_mode="html",
                link_preview=link_preview,
                silent=silent,
                buttons=buttons,
                reply_to=reply_to,
            )
        return _TelegramHttpShim(True, 200, "")
    except Exception as e:
        logger.warning("Telegram MTProto send failed: %s", e)
        msg = str(e).replace('"', "'")[:300]
        return _TelegramHttpShim(False, 500, f'{{"description":"{msg}"}}')
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def mtproto_send(
    *,
    token: str,
    chat_id: str,
    text: str,
    link_url: Optional[str],
    button_emoji: str,
    image_bytes: Optional[bytes],
    caption: str,
    disable_notification: bool,
    link_preview_large: bool,
    message_thread_id: Optional[int],
    timeout_sec: int,
    request_retries: int,
) -> _TelegramHttpShim:
    coro = _mtproto_send_inner(
        token=token,
        chat_id=chat_id,
        text=text,
        link_url=link_url,
        button_emoji=button_emoji,
        image_bytes=image_bytes,
        caption=caption,
        disable_notification=disable_notification,
        link_preview_large=link_preview_large,
        message_thread_id=message_thread_id,
        timeout_sec=timeout_sec,
        request_retries=request_retries,
    )
    return _run_coro_sync(coro)


def telegram_proxy_type() -> str:
    from app_config.app_config import app_config

    t = (app_config.get("notifications.telegram_proxy_type") or "socks_http").strip().lower()
    if t in ("", "none", "direct", "off"):
        return "none"
    if t == "mtproto":
        return "mtproto"
    return "socks_http"
