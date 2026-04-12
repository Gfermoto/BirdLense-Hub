"""Тесты окна «услышан» для снимка FIFO BirdNET."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app_config.birdnet_fifo_hearing_state import (
    build_species_fifo_table_rows,
    build_species_hearing_state,
)


def test_build_species_hearing_state_fresh_vs_stale():
    now = datetime(2026, 4, 10, 15, 0, 0, tzinfo=timezone.utc)
    events = [
        {"species": "A", "timestamp": now.isoformat()},
        {"species": "B", "timestamp": (now - timedelta(hours=30)).isoformat()},
    ]
    out = build_species_hearing_state(events, now=now, active_within_hours=24)
    assert out["active_within_hours"] == 24.0
    by = out["by_species"]
    assert by["A"]["active"] == 1
    assert by["B"]["active"] == 0


def test_repeated_singing_updates_last_heard():
    now = datetime(2026, 4, 10, 18, 0, 0, tzinfo=timezone.utc)
    events = [
        {"species": "Tit", "timestamp": (now - timedelta(hours=20)).isoformat()},
        {"species": "Tit", "timestamp": (now - timedelta(hours=2)).isoformat()},
    ]
    out = build_species_hearing_state(events, now=now, active_within_hours=24)
    assert out["by_species"]["Tit"]["active"] == 1
    assert out["by_species"]["Tit"]["seconds_since_heard"] == 2 * 3600


def test_build_species_fifo_table_rows_sorts_active_first_and_counts():
    """Таблица UI: сначала active=1, затем по имени; event_count из переданного словаря."""
    now = datetime(2026, 4, 10, 15, 0, 0, tzinfo=timezone.utc)
    events = [
        {"species": "Zed", "timestamp": now.isoformat()},
        {"species": "Zed", "timestamp": now.isoformat()},
        {"species": "Amy", "timestamp": (now - timedelta(hours=30)).isoformat()},
    ]
    counts = {"Zed": 2, "Amy": 1}
    rows = build_species_fifo_table_rows(
        events,
        now=now,
        active_within_hours=24,
        species_mapping={},
        merge_db_path=None,
        species_counts=counts,
    )
    assert len(rows) == 2
    assert rows[0]["display_label"] == "Zed"
    assert rows[0]["active"] == 1
    assert rows[0]["event_count"] == 2
    assert rows[1]["display_label"] == "Amy"
    assert rows[1]["active"] == 0
    assert rows[1]["event_count"] == 1
    for r in rows:
        assert "canonical_for_video" in r
        assert "last_heard_at" in r
        assert isinstance(r["seconds_since_heard"], int)
