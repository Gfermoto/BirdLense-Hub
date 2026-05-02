"""Synthetic tests for detector continuity and baseline protocol scripts (#402)."""

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_script_module(rel_path: str, module_name: str):
    path = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlDetectorContinuityReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_script_module("scripts/ml_detector_continuity_report.py", "ml_detector_continuity_report")

    def _create_db(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE video (
              id INTEGER PRIMARY KEY,
              start_time TEXT NOT NULL
            );
            CREATE TABLE video_species (
              id INTEGER PRIMARY KEY,
              video_id INTEGER NOT NULL,
              source TEXT NOT NULL,
              detection_provider TEXT,
              track_id INTEGER,
              frames TEXT
            );
            CREATE TABLE activity_log (
              id INTEGER PRIMARY KEY,
              type TEXT NOT NULL,
              created_at TEXT NOT NULL,
              data TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def test_continuity_report_passes_when_tracks_and_bboxes_present(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "birdlense.db"
            self._create_db(db)
            conn = sqlite3.connect(db)
            conn.execute("INSERT INTO video (id, start_time) VALUES (1, '2026-05-01T10:00:00+00:00')")
            conn.execute(
                """
                INSERT INTO video_species (id, video_id, source, detection_provider, track_id, frames)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    1,
                    "video",
                    "yolo",
                    101,
                    json.dumps([{"t": 1.2, "bbox": [0.1, 0.1, 0.4, 0.5]}]),
                ),
            )
            conn.execute(
                """
                INSERT INTO activity_log (type, created_at, data)
                VALUES (?, ?, ?)
                """,
                (
                    "decision_trace",
                    "2026-05-01T10:00:10+00:00",
                    json.dumps(
                        {
                            "video_id": 1,
                            "recording_context": {
                                "triggered_by": "live",
                                "runtime_signals": {
                                    "yolo_frames_ran": 12,
                                    "yolo_frames_with_tracks": 5,
                                },
                            },
                            "persisted_tracks": [{"track_id": 101}],
                        }
                    ),
                ),
            )
            conn.commit()
            conn.close()

            report = self.mod.build_detector_continuity_report(db_path=str(db), days=365)
            self.assertEqual(report["schema"], "detector_continuity_report@v1")
            self.assertTrue(report["ok"])
            self.assertEqual(report["rows"]["yolo_like_rows_total"], 1)
            self.assertEqual(report["rows"]["yolo_like_rows_with_track_id"], 1)
            self.assertEqual(report["rows"]["yolo_like_rows_with_bbox_frames"], 1)

    def test_continuity_report_fails_when_track_or_bbox_missing(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "birdlense.db"
            self._create_db(db)
            conn = sqlite3.connect(db)
            conn.execute("INSERT INTO video (id, start_time) VALUES (1, '2026-05-01T10:00:00+00:00')")
            conn.execute(
                """
                INSERT INTO video_species (id, video_id, source, detection_provider, track_id, frames)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    1,
                    "video",
                    "yolo",
                    None,
                    json.dumps([]),
                ),
            )
            conn.commit()
            conn.close()

            report = self.mod.build_detector_continuity_report(db_path=str(db), days=365, min_track_ratio=1.0, min_crop_ratio=1.0)
            self.assertFalse(report["ok"])
            self.assertEqual(report["rows"]["yolo_like_rows_total"], 1)
            self.assertEqual(report["rows"]["yolo_like_rows_with_track_id"], 0)
            self.assertEqual(report["rows"]["yolo_like_rows_with_bbox_frames"], 0)


class TestMlBaselineProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_script_module("scripts/ml_baseline_protocol.py", "ml_baseline_protocol")

    def test_protocol_gate_passes_when_candidate_not_worse(self):
        baseline = {
            "report_format": "benchmark_track_regen@v1",
            "videos": [
                {"label_eval": {"gold_species_recall": 0.80}},
                {"label_eval": {"gold_species_recall": 0.90}},
            ],
        }
        candidate = {
            "report_format": "benchmark_track_regen@v1",
            "videos": [
                {"label_eval": {"gold_species_recall": 0.82}, "yolo_silent_clip_rate": 0.10},
                {"label_eval": {"gold_species_recall": 0.92}, "yolo_silent_clip_rate": 0.10},
            ],
        }
        continuity = {"schema": "detector_continuity_report@v1", "metrics": {"track_gate_ok": True, "crop_gate_ok": True}}
        report = self.mod.build_baseline_protocol_report(
            baseline_report=baseline,
            candidate_report=candidate,
            continuity_report=continuity,
            max_recall_drop=0.02,
            max_yolo_silent_clip_rate=0.2,
        )
        self.assertTrue(report["ok"])
        self.assertTrue(report["gates"]["quality_recall_gate_ok"])
        self.assertTrue(report["gates"]["quality_yolo_silent_gate_ok"])

    def test_protocol_gate_fails_on_recall_drop(self):
        baseline = {
            "report_format": "benchmark_track_regen@v1",
            "videos": [
                {"label_eval": {"gold_species_recall": 0.95}},
            ],
        }
        candidate = {
            "report_format": "benchmark_track_regen@v1",
            "videos": [
                {"label_eval": {"gold_species_recall": 0.80}, "yolo_silent_clip_rate": 0.05},
            ],
        }
        report = self.mod.build_baseline_protocol_report(
            baseline_report=baseline,
            candidate_report=candidate,
            continuity_report=None,
            max_recall_drop=0.05,
            max_yolo_silent_clip_rate=0.2,
        )
        self.assertFalse(report["ok"])
        self.assertFalse(report["gates"]["quality_recall_gate_ok"])


if __name__ == "__main__":
    unittest.main()
