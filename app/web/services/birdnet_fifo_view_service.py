"""Чтение очереди BirdNET из hub БД для UI/API (#269); формат как у JSON-снимка процессора."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone

from app_config.app_config import app_config
from app_config.birdnet_merge_key import sqlite_path_for_birdnet_merge
from app_config.birdnet_fifo_hearing_state import (
    build_species_fifo_table_rows,
    build_species_hearing_state,
)
from sqlalchemy import inspect as sa_inspect

from models import BirdnetFifoEvent, db

logger = logging.getLogger(__name__)

_EXPORT_KEYS = frozenset(
    {
        "species",
        "common_name",
        "scientific_name",
        "species_code",
        "confidence",
        "timestamp",
        "source",
        "audio_source",
    }
)


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


def _parse_iso8601_utc(value) -> datetime | None:
    return _parse_ts(value)


def sanitize_birdnet_event_for_export(ev: dict) -> dict:
    out: dict = {}
    for k in _EXPORT_KEYS:
        if k not in ev:
            continue
        v = ev[k]
        if v is None:
            continue
        if k == "confidence":
            try:
                out[k] = round(float(v), 4)
            except (TypeError, ValueError):
                continue
        else:
            out[k] = v
    return out


def birdnet_fifo_cap_from_config() -> int:
    """Согласовано с MQTTEventAggregator._birdnet_event_cap."""
    raw = app_config.get("mqtt.max_events")
    try:
        m = int(raw) if raw not in (None, "") else 500
    except (TypeError, ValueError):
        m = 500
    return max(1000, max(m, 1) * 20)


def prune_birdnet_event_list_db_view(
    events: list[dict],
    *,
    now: datetime,
    ttl_hours: float,
    cap: int,
) -> list[dict]:
    """Та же семантика, что в процессоре birdnet_fifo_persist.prune_birdnet_event_list."""
    try:
        ttl_hours = float(ttl_hours)
    except (TypeError, ValueError):
        ttl_hours = 25.0
    ttl_hours = max(1.0, min(ttl_hours, 168.0))
    low_epoch = now.timestamp() - (ttl_hours * 3600.0)
    kept: list[dict] = []
    for ev in events:
        ts_epoch = ev.get("_ts_epoch")
        if ts_epoch is None:
            ts = _parse_iso8601_utc(ev.get("timestamp"))
            if ts is None:
                continue
            ts_epoch = ts.timestamp()
            ev["_ts_epoch"] = ts_epoch
        else:
            ts = _parse_iso8601_utc(ev.get("timestamp"))
            if ts is not None:
                parsed_epoch = ts.timestamp()
                if abs(float(parsed_epoch) - float(ts_epoch)) > 1.0:
                    ts_epoch = parsed_epoch
                    ev["_ts_epoch"] = ts_epoch
        if float(ts_epoch) >= low_epoch:
            kept.append(ev)
    overflow = max(0, len(kept) - int(cap))
    if overflow:
        kept = kept[overflow:]
    return kept


def build_birdnet_fifo_snapshot_payload(
    *,
    events: list[dict],
    fifo_cap: int,
    mqtt_connected: bool,
    processor_pid: int,
    recent_limit: int,
    now: datetime | None = None,
    hearing_active_hours: float | None = None,
) -> dict:
    recent_limit = max(0, min(int(recent_limit or 80), 500))
    sanitized_all = [sanitize_birdnet_event_for_export(ev) for ev in events]
    species_counter: Counter[str] = Counter()
    epochs: list[float] = []
    for ev in events:
        label = str(ev.get("species") or ev.get("common_name") or "").strip() or "unknown"
        species_counter[label] += 1
        ts = _parse_ts(ev.get("timestamp"))
        if ts is not None:
            epochs.append(ts.timestamp())
        elif ev.get("_ts_epoch") is not None:
            try:
                epochs.append(float(ev["_ts_epoch"]))
            except (TypeError, ValueError):
                pass

    oldest = newest = None
    if epochs:
        oldest = datetime.fromtimestamp(min(epochs), tz=timezone.utc).isoformat()
        newest = datetime.fromtimestamp(max(epochs), tz=timezone.utc).isoformat()

    recent = sanitized_all[-recent_limit:] if recent_limit else []

    now_utc = now or datetime.now(timezone.utc)
    if hearing_active_hours is None:
        try:
            hearing_active_hours = float(app_config.get("processor.birdnet_fifo_hearing_active_hours", 24))
        except (TypeError, ValueError):
            hearing_active_hours = 24.0
    species_hearing = build_species_hearing_state(
        events,
        now=now_utc,
        active_within_hours=hearing_active_hours,
    )
    counts_dict = dict(species_counter.most_common())
    species_mapping = app_config.get("detection.species_mapping") or {}
    species_fifo_table = build_species_fifo_table_rows(
        events,
        now=now_utc,
        active_within_hours=hearing_active_hours,
        species_mapping=species_mapping,
        merge_db_path=sqlite_path_for_birdnet_merge(),
        species_counts=counts_dict,
    )
    cap = int(fifo_cap) if fifo_cap else 0
    fill_ratio = min(1.0, float(len(events)) / float(cap)) if cap > 0 else 0.0

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "processor_pid": int(processor_pid),
        "mqtt_connected": bool(mqtt_connected),
        "queue_len": len(events),
        "fifo_cap": int(fifo_cap),
        "fifo_fill_ratio": round(fill_ratio, 4),
        "species_counts": counts_dict,
        "species_hearing": species_hearing,
        "species_fifo_table": species_fifo_table,
        "oldest_timestamp": oldest,
        "newest_timestamp": newest,
        "recent": recent,
    }


def try_build_birdnet_fifo_snapshot_from_db() -> dict | None:
    """Если таблица есть и чтение успешно — тело ответа diagnostics (без HTTP). Иначе None."""
    try:
        if not sa_inspect(db.engine).has_table("birdnet_fifo_event"):
            return None
    except Exception:
        logger.debug("birdnet_fifo_event table check failed", exc_info=True)
        return None

    try:
        rows = db.session.query(BirdnetFifoEvent).order_by(BirdnetFifoEvent.id.asc()).all()
    except Exception:
        logger.debug("birdnet_fifo_event query failed", exc_info=True)
        return None

    if not rows:
        try:
            recent_limit = int(app_config.get("processor.birdnet_fifo_snapshot_recent_limit") or 80)
        except (TypeError, ValueError):
            recent_limit = 80
        cap = birdnet_fifo_cap_from_config()
        snapshot = build_birdnet_fifo_snapshot_payload(
            events=[],
            fifo_cap=cap,
            mqtt_connected=False,
            processor_pid=0,
            recent_limit=recent_limit,
        )
        snapshot["persist_source"] = "sqlite"
        return {
            "available": True,
            "snapshot_source": "sqlite",
            "db_row_count": 0,
            "snapshot": snapshot,
        }

    events: list[dict] = []
    for r in rows:
        pl = r.payload
        if isinstance(pl, str):
            try:
                pl = json.loads(pl)
            except json.JSONDecodeError:
                continue
        if not isinstance(pl, dict):
            continue
        ev = dict(pl)
        ev["_ts_epoch"] = float(r.ts_epoch)
        events.append(ev)

    try:
        ttl_h = float(app_config.get("processor.birdnet_mqtt_prior_ttl_hours", 25))
    except (TypeError, ValueError):
        ttl_h = 25.0
    cap = birdnet_fifo_cap_from_config()
    pruned = prune_birdnet_event_list_db_view(
        events,
        now=datetime.now(timezone.utc),
        ttl_hours=ttl_h,
        cap=cap,
    )
    try:
        recent_limit = int(app_config.get("processor.birdnet_fifo_snapshot_recent_limit") or 80)
    except (TypeError, ValueError):
        recent_limit = 80

    snapshot = build_birdnet_fifo_snapshot_payload(
        events=pruned,
        fifo_cap=cap,
        mqtt_connected=False,
        processor_pid=0,
        recent_limit=recent_limit,
    )
    snapshot["persist_source"] = "sqlite"

    return {
        "available": True,
        "snapshot_source": "sqlite",
        "db_row_count": len(rows),
        "snapshot": snapshot,
    }
