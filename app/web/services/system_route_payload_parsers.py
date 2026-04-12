"""Разбор JSON payload для admin/system маршрутов (#265)."""

from __future__ import annotations


def parse_video_ids(payload) -> list[int]:
    """Список положительных int из ``payload['video_ids']``."""
    raw = (payload or {}).get("video_ids")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("video_ids must be an array of integers")
    out: list[int] = []
    for x in raw:
        try:
            v = int(x)
        except (TypeError, ValueError):
            continue
        if v > 0:
            out.append(v)
    return sorted(set(out))
