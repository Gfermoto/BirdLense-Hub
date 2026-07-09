"""Classifier calibration report (#507)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from services.classifier_calibration_report import (
    CorrectionRow,
    build_report,
    recommend_binary_thresholds,
)


def _mk_db(tmp_path: Path) -> Path:
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE species (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE video_species (
            id INTEGER PRIMARY KEY,
            video_id INTEGER,
            track_id INTEGER,
            confidence REAL,
            detection_provider TEXT,
            classifier_entropy REAL,
            classifier_top1_top2_margin REAL,
            classifier_needs_review INTEGER,
            review_reason TEXT
        );
        CREATE TABLE activity_log (
            id INTEGER PRIMARY KEY,
            type TEXT,
            data TEXT,
            created_at TEXT DEFAULT '2026-01-01'
        );
        INSERT INTO species (id, name) VALUES (1, 'Eurasian Blue Tit'), (2, 'Wood Mouse');
        INSERT INTO video_species (
            id, video_id, track_id, confidence, detection_provider,
            classifier_entropy, classifier_top1_top2_margin,
            classifier_needs_review, review_reason
        )
        VALUES (10, 1001, 501, 0.42, 'yolo', 1.33, 0.01, 1, 'classifier_uncertainty');
        """
    )
    payload = json.dumps(
        {
            "detection_id": 10,
            "from_species_name": "Wood Mouse",
            "to_species_name": "Eurasian Blue Tit",
            "source": "unknowns",
        }
    )
    con.execute(
        "INSERT INTO activity_log (type, data) VALUES ('species_correction', ?)",
        (payload,),
    )
    con.commit()
    con.close()
    return db


def test_confusion_pairs_from_activity_log(tmp_path):
    db = _mk_db(tmp_path)
    report = build_report(db, pair_limit=5)
    assert report["corrections_analyzed"] == 1
    assert report["top_confusion_pairs"][0]["from"] == "Wood Mouse"


def test_recommend_thresholds_rodent_to_bird():
    rows = [
        CorrectionRow(
            detection_id=1,
            video_id=10,
            track_id=101,
            from_name="Wood Mouse",
            to_name="Eurasian Blue Tit",
            confidence=0.35,
            detection_provider="yolo",
            source="unknowns",
            classifier_entropy=1.2,
            classifier_top1_top2_margin=0.01,
            classifier_needs_review=True,
            review_reason="classifier_uncertainty",
        ),
        CorrectionRow(
            detection_id=2,
            video_id=10,
            track_id=102,
            from_name="Wood Mouse",
            to_name="Great Tit",
            confidence=0.28,
            detection_provider="yolo",
            source="video",
            classifier_entropy=1.0,
            classifier_top1_top2_margin=0.03,
            classifier_needs_review=True,
            review_reason="classifier_uncertainty",
        ),
    ]
    rec = recommend_binary_thresholds(rows)
    assert "min_confidence_binary_bird" in rec["recommended_processor_yaml"]
    assert rec["recommended_processor_yaml"]["bird_skip_classifier_max_area_frac"] == 0.015


def test_build_report_contains_s3_sections(tmp_path):
    db = _mk_db(tmp_path)
    report = build_report(db, pair_limit=5)
    assert "session_consensus" in report
    assert "calibration_metrics" in report
    assert "unknown_ood_dashboard" in report
    assert "long_tail_report" in report
