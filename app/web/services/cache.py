"""TTL-кэш ответов: in-memory или Redis (REDIS_URL) для нескольких воркеров/реплик."""
from __future__ import annotations

import json
import math
import os
import pickle
import threading
import time
from typing import Any, Callable

KEY_ROOT = "bl:v1:"

_lock = threading.Lock()
_store: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at monotonic)

_redis_client = None  # lazy: Redis | False
_redis_warned = False


def _redis():
    """Lazy Redis client; False = отключён; None = ещё не пробовали."""
    global _redis_client, _redis_warned
    if _redis_client is not None:
        return _redis_client if _redis_client is not False else None
    url = (os.environ.get("REDIS_URL") or "").strip()
    if not url:
        _redis_client = False
        return None
    try:
        import redis as redis_lib

        _redis_client = redis_lib.from_url(
            url,
            decode_responses=False,
            socket_connect_timeout=2.5,
            socket_timeout=2.5,
        )
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        _redis_client = False
        if not _redis_warned:
            import logging

            logging.getLogger(__name__).warning(
                "REDIS_URL задан, но подключение к Redis не удалось (%s) — используется in-memory кэш.",
                e,
            )
            _redis_warned = True
        return None


def _full_key(key: str) -> str:
    return KEY_ROOT + key


def _serialize(value: Any) -> bytes:
    try:
        return b"j" + json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")
    except (TypeError, ValueError):
        return b"p" + pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)


def _deserialize(raw: bytes | None) -> Any:
    if not raw:
        return None
    if raw[0:1] == b"j":
        return json.loads(raw[1:].decode("utf-8"))
    if raw[0:1] == b"p":
        return pickle.loads(raw[1:])
    return pickle.loads(raw)


def cache_get(key: str) -> tuple[bool, Any]:
    r = _redis()
    if r is not None:
        try:
            raw = r.get(_full_key(key))
            if raw is None:
                return False, None
            return True, _deserialize(raw)
        except Exception:
            return False, None

    with _lock:
        entry = _store.get(key)
    if entry is None:
        return False, None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        with _lock:
            _store.pop(key, None)
        return False, None
    return True, value


def cache_set(key: str, value: Any, ttl_seconds: float) -> None:
    ttl = max(1, int(math.ceil(ttl_seconds)))
    r = _redis()
    if r is not None:
        try:
            r.setex(_full_key(key), ttl, _serialize(value))
            return
        except Exception:
            pass
    with _lock:
        _store[key] = (value, time.monotonic() + ttl_seconds)


def cache_delete(key: str) -> None:
    r = _redis()
    if r is not None:
        try:
            r.delete(_full_key(key))
        except Exception:
            pass
    with _lock:
        _store.pop(key, None)


def cache_delete_prefix(prefix: str) -> None:
    pattern = _full_key(prefix) + "*"
    r = _redis()
    if r is not None:
        try:
            for k in r.scan_iter(match=pattern, count=200):
                r.delete(k)
        except Exception:
            pass
    with _lock:
        keys = [k for k in _store if k.startswith(prefix)]
        for k in keys:
            del _store[k]


def cached(key_fn: Callable[..., str], ttl_seconds: float):
    """Декоратор: @cached(lambda: 'key', ttl_seconds=60)"""

    def decorator(fn):
        import functools

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            found, val = cache_get(key)
            if found:
                return val
            result = fn(*args, **kwargs)
            cache_set(key, result, ttl_seconds)
            return result

        return wrapper

    return decorator
