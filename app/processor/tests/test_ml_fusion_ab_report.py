"""Synthetic tests for scripts/ml_fusion_ab_report.py (fusion A/B gate)."""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, '../../..'))
_scripts_path = os.path.join(_repo_root, 'scripts')
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _mk_db() -> str:
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE video (
              id INTEGER PRIMARY KEY,
              video_path TEXT,
              processor_version TEXT,
              start_time TEXT,
              end_time TEXT,
              deleted_at TEXT
            );
            CREATE TABLE species (
              id INTEGER PRIMARY KEY,
              name TEXT
            );
            CREATE TABLE video_species (
              id INTEGER PRIMARY KEY,
              video_id INTEGER,
              species_id INTEGER,
              start_time REAL,
              end_time REAL,
              confidence REAL,
              source TEXT,
              detection_provider TEXT,
              track_id INTEGER,
              created_at TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


class TestMlFusionAbReport(unittest.TestCase):
    """Fusion A/B health metrics from SQLite snapshots."""

    def test_report_ok_when_yolo_share_and_duplicates_are_good(self):
        """Report is green for healthy provider mix and no duplicates."""
        from ml_fusion_ab_report import build_fusion_ab_report_from_db

        db_path = _mk_db()
        now = datetime.now(timezone.utc)
        t1 = now.isoformat()
        t2 = (now + timedelta(seconds=20)).isoformat()
        try:
            conn = sqlite3.connect(db_path)
            conn.executemany(
                'INSERT INTO species (id, name) VALUES (?, ?)',
                [
                    (1, 'Bird'),
                    (2, 'Great Tit'),
                    (3, 'Blue Tit'),
                ],
            )
            conn.executemany(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                [
                    (1, '/a.mp4', 'v1', t1, t2),
                    (2, '/b.mp4', 'v1', t1, t2),
                ],
            )
            conn.executemany(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        1, 1, 2, 0.0, 4.0, 0.72,
                        'video', 'yolo', 10, now.isoformat(),
                    ),
                    (
                        2, 1, 3, 5.0, 8.0, 0.66,
                        'video', 'yolo', 11, now.isoformat(),
                    ),
                    (
                        3, 2, 2, 0.0, 6.0, 0.74,
                        'video', 'frigate', 21, now.isoformat(),
                    ),
                ],
            )
            conn.commit()
            conn.close()

            out = build_fusion_ab_report_from_db(
                db_path=db_path,
                days=14,
                min_yolo_share=0.30,
                max_duplicate_video_groups=0,
                max_duplicate_detection_groups=0,
                max_generic_overlap_ratio=0.80,
                max_calendar_delta_ratio=5.0,
                calendar_compare_totals={
                    'encounters': 10,
                    'max_simultaneous': 14,
                    'delta': 4,
                },
            )
            self.assertTrue(out['ok'])
            self.assertEqual(out['metrics']['duplicate_video_groups'], 0)
            self.assertEqual(out['metrics']['duplicate_detection_groups'], 0)
            self.assertGreater(out['metrics']['yolo_share_vs_frigate'], 0.30)
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_report_fails_when_duplicates_and_low_yolo_share(self):
        """Report turns red for duplicated groups and weak YOLO presence."""
        from ml_fusion_ab_report import build_fusion_ab_report_from_db

        db_path = _mk_db()
        now = datetime.now(timezone.utc)
        t1 = now.isoformat()
        t2 = (now + timedelta(seconds=20)).isoformat()
        try:
            conn = sqlite3.connect(db_path)
            conn.executemany(
                'INSERT INTO species (id, name) VALUES (?, ?)',
                [
                    (1, 'Bird'),
                    (2, 'Great Tit'),
                ],
            )
            conn.executemany(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                [
                    (1, '/dup.mp4', 'v1', t1, t2),
                    (2, '/dup.mp4', 'v1', t1, t2),
                ],
            )
            conn.executemany(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        1, 1, 2, 0.0, 5.0, 0.81,
                        'video', 'frigate', 33, now.isoformat(),
                    ),
                    (
                        2, 1, 2, 0.0, 5.0, 0.81,
                        'video', 'frigate', 33, now.isoformat(),
                    ),
                    (
                        3, 2, 2, 0.0, 5.0, 0.83,
                        'video', 'frigate', 44, now.isoformat(),
                    ),
                ],
            )
            conn.commit()
            conn.close()

            out = build_fusion_ab_report_from_db(
                db_path=db_path,
                days=14,
                min_yolo_share=0.30,
                max_duplicate_video_groups=0,
                max_duplicate_detection_groups=0,
                max_generic_overlap_ratio=0.60,
                max_calendar_delta_ratio=1.0,
                calendar_compare_totals={
                    'encounters': 1,
                    'max_simultaneous': 6,
                    'delta': 5,
                },
            )
            self.assertFalse(out['ok'])
            self.assertFalse(out['gates']['yolo_share_ok'])
            self.assertFalse(out['gates']['duplicate_video_groups_ok'])
            self.assertFalse(out['gates']['duplicate_detection_groups_ok'])
            self.assertFalse(out['gates']['calendar_delta_ratio_ok'])
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main()
