"""Простой процессный TTL-кэш для дорогих запросов и внешних API."""
import time
import threading
from typing import Any, Callable

_lock = threading.Lock()
_store: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)


def cache_get(key: str) -> tuple[bool, Any]:
    """Вернуть (found, value). Expired → found=False."""
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
    """Store value under key with a TTL."""
    with _lock:
        _store[key] = (value, time.monotonic() + ttl_seconds)


def cache_delete(key: str) -> None:
    """Remove a single key from the cache."""
    with _lock:
        _store.pop(key, None)


def cache_delete_prefix(prefix: str) -> None:
    """Remove all keys that start with prefix."""
    with _lock:
        keys = [k for k in _store if k.startswith(prefix)]
        for k in keys:
            del _store[k]


def cached(key_fn: Callable[..., str], ttl_seconds: float):
    """Decorator that caches the wrapped function result with a TTL.

    Usage: @cached(lambda *a, **kw: 'key', ttl_seconds=60)
    """
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
