"""POST /api/ui/system/behavior-baseline/retrain — обучение из меток в БД (#416)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def _behavior_retrain_env(app, monkeypatch, tmp_path):
    from app_config.app_config import app_config

    from services import behavior_baseline_retrain_service as m

    monkeypatch.setattr(
        m,
        "resolve_behavior_export_write_path",
        lambda: tmp_path / "behavior_logistic_export@v1.json",
    )
    old_admin = app_config.get("general.settings_password")
    app_config.set("general.settings_password", "")
    yield
    app_config.set("general.settings_password", old_admin)


def test_behavior_retrain_403_when_settings_locked(app, client):
    from app_config.app_config import app_config

    old = app_config.get("general.settings_password")
    app_config.set("general.settings_password", "behavior-retrain-lock")
    try:
        r = client.post("/api/ui/system/behavior-baseline/retrain", json={})
        assert r.status_code == 403
        assert r.get_json().get("error") == "Password required"
    finally:
        app_config.set("general.settings_password", old)


def test_behavior_retrain_400_too_few_labels(app, client, _behavior_retrain_env):
    from models import Video, db

    with app.app_context():
        v = Video(
            processor_version="t",
            start_time=datetime(2026, 5, 1, 8, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 1, 8, 0, 20, tzinfo=timezone.utc),
            video_path="data/recordings/behavior/a.mp4",
            behavior_label="eat",
        )
        db.session.add(v)
        db.session.commit()

    r = client.post("/api/ui/system/behavior-baseline/retrain", json={})
    assert r.status_code == 400
    assert "4" in (r.get_json().get("error") or "")


def test_behavior_retrain_200_writes_export(app, client, _behavior_retrain_env):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        sp = Species(name="Behavior Retrain Finch")
        db.session.add(sp)
        db.session.flush()
        frames = json.dumps([{"t": 0.1, "bbox": [0, 0, 1, 1]}])
        for i, lab in enumerate(("eat", "eat", "drink", "drink")):
            v = Video(
                processor_version="t",
                start_time=datetime(2026, 5, 2, 8, i, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 5, 2, 8, i, 30, tzinfo=timezone.utc),
                video_path=f"data/recordings/behavior/v{i}.mp4",
                behavior_label=lab,
            )
            db.session.add(v)
            db.session.flush()
            vs = VideoSpecies(
                video_id=v.id,
                species_id=sp.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.9,
                source="video",
                frames=frames,
            )
            db.session.add(vs)
        db.session.commit()

    r = client.post("/api/ui/system/behavior-baseline/retrain", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("n_training_videos") == 4
    assert set(body.get("labels") or []) == {"drink", "eat"}
    path = body.get("export_path")
    assert path
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload.get("schema") == "behavior_logistic_export@v1"
    assert payload.get("training_source") == "ui_hub_retrain"
