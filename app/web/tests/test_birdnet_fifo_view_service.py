"""BirdNET FIFO из SQLite в diagnostics (#269)."""

from __future__ import annotations

from datetime import datetime, timezone

from models import BirdnetFifoEvent, db


def test_build_birdnet_fifo_snapshot_prefers_db(app):
    with app.app_context():
        from services.system_diagnostics_service import (
            build_birdnet_fifo_snapshot_response,
        )

        now = datetime.now(timezone.utc)
        ev = {
            "species": "DB Finch",
            "timestamp": now.isoformat(),
            "source": "birdnet",
            "confidence": 0.88,
        }
        db.session.add(BirdnetFifoEvent(ts_epoch=now.timestamp(), payload=ev))
        db.session.commit()

        body, code = build_birdnet_fifo_snapshot_response()
        assert code == 200
        assert body.get("snapshot_source") == "sqlite"
        assert body.get("available") is True
        snap = body.get("snapshot") or {}
        assert snap.get("queue_len", 0) >= 1
        assert snap.get("persist_source") == "sqlite"
        assert snap.get("mqtt_connected") is None
        recent = snap.get("recent") or []
        assert any(r.get("species") == "DB Finch" for r in recent)
        assert "species_hearing" in snap
        assert "fifo_fill_ratio" in snap
        hearing = (snap.get("species_hearing") or {}).get("by_species") or {}
        assert hearing.get("DB Finch", {}).get("active") == 1

        table = snap.get("species_fifo_table") or []
        assert isinstance(table, list)
        finch = [r for r in table if r.get("display_label") == "DB Finch"]
        assert len(finch) == 1
        row = finch[0]
        assert row.get("active") == 1
        assert row.get("event_count", 0) >= 1
        assert "canonical_for_video" in row
        assert isinstance(row.get("canonical_for_video"), str)
        assert row.get("last_heard_at")
        assert isinstance(row.get("seconds_since_heard"), int)


def test_birdnet_fifo_table_accumulates_via_orm(app):
    """Строки birdnet_fifo_event накапливаются при последовательных INSERT."""
    with app.app_context():
        from models import BirdnetFifoEvent, db

        before = db.session.query(BirdnetFifoEvent).count()
        now = datetime.now(timezone.utc)
        for i in range(5):
            db.session.add(
                BirdnetFifoEvent(
                    ts_epoch=now.timestamp() + i * 0.01,
                    payload={
                        "species": f"Stack Test {i}",
                        "timestamp": now.isoformat(),
                        "source": "birdnet",
                        "confidence": 0.7,
                    },
                )
            )
        db.session.commit()
        after = db.session.query(BirdnetFifoEvent).count()
        assert after == before + 5
