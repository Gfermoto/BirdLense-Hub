"""Smoke tests for POST /api/processor/videos (issue #202)."""

from datetime import datetime, timezone

import os

import pytest

PROC_SECRET = "pytest-processor-secret-202"


def _touch_video_file(video_path: str, *, data_root: str) -> str:
    """Create an on-disk file for a logical ``data/recordings/.../video.mp4`` path."""
    assert video_path.startswith("data/recordings/")
    # full_path_for_video resolves relative paths against dirname(DATA_DIR)
    app_base = os.path.dirname(os.path.abspath(data_root))
    full = os.path.join(app_base, video_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as handle:
        handle.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    return full


@pytest.fixture(autouse=True)
def _processor_secret_env(monkeypatch):
    monkeypatch.setenv("PROCESSOR_SECRET", PROC_SECRET)
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.setenv("FLASK_ENV", "testing")


@pytest.fixture
def proc_headers():
    return {"X-Processor-Token": PROC_SECRET, "Content-Type": "application/json"}


def _base_video_payload(folder_token: str):
    t0 = datetime.now(timezone.utc).isoformat()
    t1 = datetime.now(timezone.utc).isoformat()
    return {
        "processor_version": "pytest-1",
        "start_time": t0,
        "end_time": t1,
        "video_path": f"data/recordings/2026/04/04/{folder_token}/video.mp4",
        "spectrogram_path": "",
    }


def test_processor_videos_forbidden_wrong_token(client, monkeypatch):
    monkeypatch.setenv("PROCESSOR_SECRET", "expected-proc-secret")
    r = client.post(
        "/api/processor/videos",
        json={},
        headers={"Content-Type": "application/json", "X-Processor-Token": "wrong-token"},
    )
    assert r.status_code == 403


def test_processor_videos_missing_species_400(client, proc_headers, monkeypatch, tmp_path):
    from routes import processor_routes

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    body = _base_video_payload("090010")
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = []
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 400
    assert "missing" in (r.get_json() or {}).get("error", "").lower()


def test_processor_videos_all_below_threshold_400(client, proc_headers, monkeypatch, tmp_path):
    from app_config.app_config import app_config
    from routes import processor_routes

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.5,
    )
    body = _base_video_payload("090011")
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": "Great Tit",
            "confidence": 0.1,
            "start_time": 0,
            "end_time": 1,
            "source": "video",
            "frames": [],
        }
    ]
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 400
    err = (r.get_json() or {}).get("error", "")
    assert "threshold" in err.lower() or "below" in err.lower()


def test_processor_videos_rejects_empty_yolo_bbox_rows(
    client,
    proc_headers,
    monkeypatch,
    tmp_path,
):
    from app_config.app_config import app_config
    from routes import processor_routes

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    body = _base_video_payload("090012")
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": "Great Tit",
            "confidence": 0.9,
            "start_time": 0,
            "end_time": 1,
            "source": "video",
            "detection_provider": "yolo",
            "frames": [],
        }
    ]
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 400
    payload = r.get_json() or {}
    assert payload.get("reason") == "video_bbox_track_contract_empty"


def test_processor_videos_prunes_invalid_yolo_rows_but_keeps_valid(
    app,
    client,
    proc_headers,
    monkeypatch,
    tmp_path,
):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Species, Video, VideoSpecies, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(
        vp_mod,
        "update_species_info_from_wiki",
        lambda *_a, **_k: None,
        raising=False,
    )
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")
    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(f"{(int(token)+1) % 1000000:06d}")
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest Invalid {token}",
            "confidence": 0.9,
            "start_time": 0,
            "end_time": 1,
            "source": "video",
            "detection_provider": "yolo",
            "frames": [{"t": 0.1, "bbox": [0.2, 0.2, 0.2, 0.4]}],
        },
        {
            "species_name": "Great Tit",
            "confidence": 0.9,
            "start_time": 0,
            "end_time": 1,
            "source": "video",
            "detection_provider": "yolo",
            "frames": [{"t": 0.1, "bbox": [0.1, 0.1, 0.3, 0.3]}],
        },
    ]
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    with app.app_context():
        assert db.session.query(Video).count() == 1
        assert db.session.query(VideoSpecies).count() == 1
        species_name = db.session.query(Species.name).join(VideoSpecies, VideoSpecies.species_id == Species.id).scalar()
        assert species_name == "Great Tit"


def test_processor_videos_rejects_missing_video_file(app, client, proc_headers, monkeypatch, tmp_path):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    body["species"] = [
        {
            "species_name": f"Pytest MissingFile {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]

    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 400, r.get_data(as_text=True)
    payload = r.get_json() or {}
    assert payload.get("reason") in {"video_file_missing", "video_file_unreadable"}
    with app.app_context():
        assert db.session.query(Video).count() == 0


def test_processor_videos_success_201(app, client, proc_headers, monkeypatch, tmp_path):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest Finch {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]

    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    data = r.get_json()
    assert "video_id" in data
    vid = data["video_id"]

    with app.app_context():
        assert db.session.get(Video, vid) is not None


def test_processor_videos_persists_behavior_label_optional(app, client, proc_headers, monkeypatch, tmp_path):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest Behavior {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]
    body["behavior_label"] = "feeding"
    body["behavior_confidence"] = 0.72

    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    vid = r.get_json()["video_id"]
    with app.app_context():
        v = db.session.get(Video, vid)
        assert v is not None
        assert v.behavior_label == "feeding"
        assert abs(float(v.behavior_confidence or 0) - 0.72) < 1e-6


def test_processor_videos_idempotent_same_payload_returns_existing(
    app,
    client,
    proc_headers,
    monkeypatch,
    tmp_path,
):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, VideoSpecies, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest Idempotent {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]

    r1 = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r1.status_code == 201, r1.get_data(as_text=True)
    first_video_id = r1.get_json()["video_id"]

    r2 = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    payload2 = r2.get_json() or {}
    assert payload2.get("duplicate") is True
    assert payload2.get("video_id") == first_video_id

    with app.app_context():
        assert db.session.query(Video).count() == 1
        assert db.session.query(VideoSpecies).count() == 1


def test_processor_videos_same_clip_key_but_payload_changed_returns_409(
    app,
    client,
    proc_headers,
    monkeypatch,
    tmp_path,
):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, VideoSpecies, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest Idempotent A {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]
    r1 = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r1.status_code == 201, r1.get_data(as_text=True)

    changed = dict(body)
    changed["species"] = [
        {
            "species_name": f"Pytest Idempotent B {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]
    r2 = client.post("/api/processor/videos", json=changed, headers=proc_headers)
    assert r2.status_code == 409, r2.get_data(as_text=True)
    payload2 = r2.get_json() or {}
    assert payload2.get("error") == "Idempotency conflict for existing clip key"

    with app.app_context():
        assert db.session.query(Video).count() == 1
        assert db.session.query(VideoSpecies).count() == 1


def test_processor_videos_same_clip_conflict_detected_when_legacy_hash_missing(
    app,
    client,
    proc_headers,
    monkeypatch,
    tmp_path,
):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, VideoSpecies, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest LegacyHash A {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]
    r1 = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r1.status_code == 201, r1.get_data(as_text=True)
    video_id = r1.get_json()["video_id"]

    with app.app_context():
        video = db.session.get(Video, video_id)
        assert video is not None
        video.ingest_payload_hash = None
        db.session.commit()

    changed = dict(body)
    changed["species"] = [
        {
            "species_name": f"Pytest LegacyHash B {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]
    r2 = client.post("/api/processor/videos", json=changed, headers=proc_headers)
    assert r2.status_code == 409, r2.get_data(as_text=True)
    payload2 = r2.get_json() or {}
    assert payload2.get("error") == "Idempotency conflict for existing clip key"

    with app.app_context():
        assert db.session.query(Video).count() == 1
        assert db.session.query(VideoSpecies).count() == 1


def test_processor_videos_idempotent_ignores_non_persisted_flags(
    app,
    client,
    proc_headers,
    monkeypatch,
    tmp_path,
):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest Canonical {token}",
            "confidence": 0.95,
            "start_time": 0.0,
            "end_time": 2.0,
            "source": "video",
            "frames": [],
            "visit_eligible": True,
            "notification_eligible": True,
            "decision_kind": "accepted_species",
            "classifier_confidence": 0.95,
        }
    ]
    r1 = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r1.status_code == 201, r1.get_data(as_text=True)
    first_video_id = r1.get_json()["video_id"]

    changed = dict(body)
    changed["species"] = [dict(body["species"][0])]
    changed["species"][0]["visit_eligible"] = False
    changed["species"][0]["notification_eligible"] = False
    changed["species"][0]["decision_kind"] = "review_only_generic"
    changed["species"][0]["classifier_confidence"] = 0.01
    r2 = client.post("/api/processor/videos", json=changed, headers=proc_headers)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    payload2 = r2.get_json() or {}
    assert payload2.get("duplicate") is True
    assert payload2.get("video_id") == first_video_id

    with app.app_context():
        assert db.session.query(Video).count() == 1


def test_processor_videos_hot_path_skips_species_metadata_enrichment(app, client, proc_headers, monkeypatch, tmp_path):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.species_metadata_enrichment_service as meta_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(
        meta_mod,
        "enrich_species_metadata",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("metadata must not be called")),
    )
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest NoMeta {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]

    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    vid = r.get_json()["video_id"]

    with app.app_context():
        assert db.session.get(Video, vid) is not None


def test_processor_videos_scales_delta_persisted_when_enabled(app, client, proc_headers, monkeypatch, tmp_path):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")
    monkeypatch.setitem(app_config.config.setdefault("integrations", {}), "scales", {"enabled": True})

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["scales_weight_delta_kg"] = 0.0234
    body["species"] = [
        {
            "species_name": f"Pytest Scale {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    vid = r.get_json()["video_id"]
    with app.app_context():
        v = db.session.get(Video, vid)
        assert v is not None
        assert abs(float(v.scales_weight_delta_kg) - 0.0234) < 1e-6

    gr = client.get(f"/api/ui/videos/{vid}")
    assert gr.status_code == 200
    js = gr.get_json()
    assert js.get("scales") is not None
    assert abs(js["scales"]["delta_kg"] - 0.0234) < 1e-6
    assert js["scales"]["display_unit"] == "g"


def test_processor_videos_scales_ignored_when_disabled(app, client, proc_headers, monkeypatch, tmp_path):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import Video, db
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")
    monkeypatch.setitem(app_config.config.setdefault("integrations", {}), "scales", {"enabled": False})

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["scales_weight_delta_kg"] = 0.05
    body["species"] = [
        {
            "species_name": f"Pytest NoScale {token}",
            "confidence": 0.95,
            "start_time": 0,
            "end_time": 2,
            "source": "video",
            "frames": [],
        }
    ]
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 201
    vid = r.get_json()["video_id"]
    with app.app_context():
        v = db.session.get(Video, vid)
        assert v.scales_weight_delta_kg is None


def test_processor_videos_invalid_iso_400(client, proc_headers, monkeypatch, tmp_path):
    from routes import processor_routes

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    _touch_video_file("data/recordings/2026/04/04/090012/video.mp4", data_root=str(tmp_path / "data"))
    body = {
        "processor_version": "x",
        "start_time": "not-a-date",
        "end_time": "also-bad",
        "video_path": "data/recordings/2026/04/04/090012/video.mp4",
        "spectrogram_path": "",
        "species": [
            {
                "species_name": "X",
                "confidence": 1,
                "start_time": 0,
                "end_time": 1,
                "source": "video",
                "frames": [],
            }
        ],
    }
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 400
    assert "datetime" in (r.get_json() or {}).get("error", "").lower()


def test_processor_videos_runtime_reid_payload_persists_nickname_and_sidecar(
    app,
    client,
    proc_headers,
    monkeypatch,
    tmp_path,
):
    from app_config.app_config import app_config
    from routes import processor_routes
    from models import VideoSpecies, db
    from sqlalchemy import text
    import services.visit_processor as vp_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(processor_routes, "fetch_weather_for_ingest", lambda: {})
    monkeypatch.setattr(vp_mod, "update_species_info_from_wiki", lambda *_a, **_k: None, raising=False)
    monkeypatch.setitem(
        app_config.config.setdefault("detection", {}),
        "min_confidence_to_store",
        0.05,
    )
    monkeypatch.setitem(app_config.config.setdefault("webhook", {}), "url", "")

    token = str(id(app))[-6:].zfill(6)
    body = _base_video_payload(token)
    _touch_video_file(body["video_path"], data_root=str(tmp_path / "data"))
    body["species"] = [
        {
            "species_name": f"Pytest Runtime ReID {token}",
            "confidence": 0.95,
            "start_time": 0.0,
            "end_time": 2.0,
            "source": "video",
            "frames": [],
            "track_id": 7,
            "individual_nickname": "Рыжик",
            "reid_model": "dinov2_vits14",
            "reid_dim": 4,
            "reid_embedding": [0.1, 0.2, 0.3, 0.4],
            "reid_crop_key": f"runtime://pytest/{token}/track/7",
        }
    ]
    r = client.post("/api/processor/videos", json=body, headers=proc_headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    payload = r.get_json() or {}
    timing = payload.get("ingest_timing_ms") or {}
    assert timing.get("total_ms", 0) >= 0
    assert "visit_processor_ms" in timing
    assert "commit_ms" in timing
    vid = payload["video_id"]
    with app.app_context():
        vs = db.session.query(VideoSpecies).filter_by(video_id=vid).first()
        assert vs is not None
        assert vs.individual_nickname == "Рыжик"
        row = (
            db.session.execute(
                text(
                    "SELECT model, dim, individual_label "
                    "FROM reid_embedding WHERE video_species_id=:vs_id "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"vs_id": vs.id},
            )
            .mappings()
            .first()
        )
        assert row is not None
        assert row["model"] == "dinov2_vits14"
        assert int(row["dim"]) == 4
        assert row["individual_label"] == "Рыжик"
