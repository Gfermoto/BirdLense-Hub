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
            confidence REAL,
            detection_provider TEXT
        );
        CREATE TABLE activity_log (
            id INTEGER PRIMARY KEY,
            type TEXT,
            data TEXT,
            created_at TEXT DEFAULT '2026-01-01'
        );
        INSERT INTO species (id, name) VALUES (1, 'Eurasian Blue Tit'), (2, 'Wood Mouse');
        INSERT INTO video_species (id, confidence, detection_provider)
        VALUES (10, 0.42, 'yolo');
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
        CorrectionRow("Wood Mouse", "Eurasian Blue Tit", 0.35, "yolo", "unknowns"),
        CorrectionRow("Wood Mouse", "Great Tit", 0.28, "yolo", "video"),
    ]
    rec = recommend_binary_thresholds(rows)
    assert "min_confidence_binary_bird" in rec["recommended_processor_yaml"]
    assert rec["recommended_processor_yaml"]["bird_skip_classifier_max_area_frac"] == 0.015
