"""Состояние «услышан / не услышан» по видам для снимка FIFO BirdNET (общий web + processor)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def event_epoch_seconds(ev: dict) -> float | None:
    """Время события в секундах UTC (epoch); приоритет timestamp, иначе _ts_epoch."""
    ts = _parse_ts(ev.get("timestamp"))
    if ts is not None:
        return ts.timestamp()
    te = ev.get("_ts_epoch")
    if te is None:
        return None
    try:
        return float(te)
    except (TypeError, ValueError):
        return None


def species_display_label(ev: dict) -> str:
    return str(ev.get("species") or ev.get("common_name") or "").strip() or "unknown"


def build_species_hearing_state(
    events: list[dict],
    *,
    now: datetime | None = None,
    active_within_hours: float = 24.0,
) -> dict[str, Any]:
    """
    Для каждого вида в текущей очереди: последнее услышивание и флаг active (1/0).

    active=1 если последнее событие вида не старше active_within_hours от now;
    иначе 0 (вид ещё может быть в FIFO из‑за TTL/cap, но «давно не пел»).
    """
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    now_dt = now_dt.astimezone(timezone.utc)
    try:
        window_sec = float(active_within_hours) * 3600.0
    except (TypeError, ValueError):
        window_sec = 86400.0
    window_sec = max(60.0, min(window_sec, 168 * 3600.0))

    last_epoch_by_label: dict[str, float] = {}
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        label = species_display_label(ev)
        ep = event_epoch_seconds(ev)
        if ep is None:
            continue
        prev = last_epoch_by_label.get(label)
        if prev is None or ep > prev:
            last_epoch_by_label[label] = ep

    now_ts = now_dt.timestamp()
    by_species: dict[str, dict[str, Any]] = {}
    for label, epoch in sorted(last_epoch_by_label.items(), key=lambda x: -x[1]):
        age_sec = max(0.0, now_ts - epoch)
        active = 1 if age_sec <= window_sec else 0
        by_species[label] = {
            "active": active,
            "last_heard_at": datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(),
            "seconds_since_heard": int(round(age_sec)),
        }

    return {
        "active_within_hours": round(window_sec / 3600.0, 4),
        "by_species": by_species,
    }


def latest_event_by_display_label(events: list) -> dict[str, dict]:
    """Последнее по времени событие для каждой строки отображения (species/common_name)."""
    best: dict[str, tuple[float, dict]] = {}
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        label = species_display_label(ev)
        if label.lower() == "unknown":
            continue
        ep = event_epoch_seconds(ev)
        if ep is None:
            continue
        prev = best.get(label)
        if prev is None or ep > prev[0]:
            best[label] = (ep, ev)
    return {k: v[1] for k, v in best.items()}


def build_species_fifo_table_rows(
    events: list,
    *,
    now: datetime | None = None,
    active_within_hours: float = 24.0,
    species_mapping: dict | None = None,
    merge_db_path: str | None = None,
    species_counts: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """
    Строки для UI-таблицы: MQTT-подпись, канон для видео, active 1/0, счётчики.
    """
    from app_config.birdnet_merge_key import birdnet_merge_key

    species_mapping = species_mapping or {}
    species_counts = species_counts or {}
    hearing = build_species_hearing_state(
        events,
        now=now,
        active_within_hours=active_within_hours,
    )
    latest = latest_event_by_display_label(events)
    rows: list[dict[str, Any]] = []
    for label, meta in hearing["by_species"].items():
        last_ev = latest.get(label) or {}
        canonical = birdnet_merge_key(last_ev, species_mapping, merge_db_path)
        sci = last_ev.get("scientific_name")
        rows.append(
            {
                "display_label": label,
                "canonical_for_video": canonical,
                "scientific_name": str(sci).strip() if sci else None,
                "active": int(meta.get("active") or 0),
                "last_heard_at": meta.get("last_heard_at"),
                "seconds_since_heard": int(meta.get("seconds_since_heard") or 0),
                "event_count": int(species_counts.get(label, 0)),
            }
        )
    rows.sort(key=lambda r: (-r["active"], str(r["display_label"]).lower()))
    return rows
