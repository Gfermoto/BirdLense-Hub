"""Tests for embedding-driven bird profile auto-link suggestions."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from models import BirdProfile, ReidTrainingPair, Species, Video, VideoSpecies, db
from services.reid_auto_link_service import (
    record_link_feedback,
    suggest_profile_links,
)


def _ensure_reid_table() -> None:
    db.session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS reid_embedding (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_species_id INTEGER,
                video_id INTEGER,
                species_id INTEGER,
                track_id INTEGER,
                crop_path TEXT NOT NULL UNIQUE,
                model TEXT NOT NULL,
                dim INTEGER NOT NULL,
                embedding_json TEXT NOT NULL,
                species_name TEXT,
                individual_label TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _insert_emb(*, vsid: int, vid: int, sid: int, emb: list[float], crop: str) -> None:
    db.session.execute(
        text(
            "INSERT INTO reid_embedding "
            "(video_species_id, video_id, species_id, track_id, crop_path, model, dim, embedding_json) "
            "VALUES (:vsid, :vid, :sid, 1, :crop, 'ornimetrics_reid', :dim, :emb)"
        ),
        {
            "vsid": int(vsid),
            "vid": int(vid),
            "sid": int(sid),
            "crop": crop,
            "dim": len(emb),
            "emb": json.dumps(emb),
        },
    )


@pytest.fixture
def reid_auto_link_setup(app):
    with app.app_context():
        species = Species(name="AutoLink Sparrow")
        db.session.add(species)
        db.session.flush()
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        video = Video(
            processor_version="test",
            video_path="/tmp/autolink.mp4",
            start_time=now,
            end_time=now,
        )
        db.session.add(video)
        db.session.flush()
        p1 = BirdProfile(display_name="Alpha", species_id=species.id)
        p2 = BirdProfile(display_name="Beta", species_id=species.id)
        db.session.add_all([p1, p2])
        db.session.flush()
        anchor = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=0.0,
            end_time=1.0,
            confidence=0.9,
            source="video",
            track_id=1,
        )
        linked = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=1.0,
            end_time=2.0,
            confidence=0.9,
            source="video",
            track_id=2,
            bird_profile_id=p2.id,
        )
        db.session.add_all([anchor, linked])
        db.session.flush()
        _ensure_reid_table()
        _insert_emb(vsid=anchor.id, vid=video.id, sid=species.id, emb=[1.0, 0.0, 0.0], crop=f"/tmp/a-{anchor.id}.jpg")
        _insert_emb(vsid=linked.id, vid=video.id, sid=species.id, emb=[0.99, 0.01, 0.0], crop=f"/tmp/b-{linked.id}.jpg")
        db.session.commit()
        yield {
            "anchor_vs_id": int(anchor.id),
            "p1_id": int(p1.id),
            "p2_id": int(p2.id),
            "species_id": int(species.id),
        }


def test_suggest_profile_links_high_similarity(app, reid_auto_link_setup):
    with app.app_context():
        payload = suggest_profile_links(video_species_id=reid_auto_link_setup["anchor_vs_id"], limit=5)
        assert payload["available"] is True
        assert payload["candidates"]
        top = payload["candidates"][0]
        assert top["profile_id"] == reid_auto_link_setup["p2_id"]
        assert top["tier"] in {"auto", "suggest"}
        assert top["similarity"] >= 0.75


def test_record_link_feedback_hard_negative(app, reid_auto_link_setup):
    with app.app_context():
        out = record_link_feedback(
            action="reject",
            candidate_profile_id=reid_auto_link_setup["p2_id"],
            video_species_id=reid_auto_link_setup["anchor_vs_id"],
            similarity=0.91,
        )
        assert out["label"] == "hard_negative"
        row = db.session.get(ReidTrainingPair, int(out["id"]))
        assert row is not None
        assert row.label == "hard_negative"
