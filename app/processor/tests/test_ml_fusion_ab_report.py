"""Synthetic tests for scripts/ml_fusion_ab_report.py (fusion A/B gate)."""

import os
import json
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
            CREATE TABLE activity_log (
              id INTEGER PRIMARY KEY,
              type TEXT,
              created_at TEXT,
              data TEXT
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
                min_yolo_share_bird_only=0.30,
                min_yolo_share_bird_only_warn=0.15,
                min_yolo_track_found_rate_warn=0.40,
                min_decision_trace_rows_warn=20,
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
            self.assertGreater(out['metrics']['yolo_bird_share_vs_frigate'], 0.30)
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
                min_yolo_share_bird_only=0.30,
                min_yolo_share_bird_only_warn=0.15,
                min_yolo_track_found_rate_warn=0.40,
                min_decision_trace_rows_warn=20,
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
            self.assertFalse(out['gates']['yolo_share_bird_only_ok'])
            self.assertFalse(out['gates']['duplicate_video_groups_ok'])
            self.assertFalse(out['gates']['duplicate_detection_groups_ok'])
            self.assertFalse(out['gates']['calendar_delta_ratio_ok'])
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_bird_only_yolo_share_gate_is_reported_separately(self):
        """Bird-only YOLO share can pass even when overall provider share is low."""
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
                    (1, 'Great Tit'),
                    (2, 'Blue Tit'),
                    (3, 'Rodent'),
                ],
            )
            conn.execute(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (1, '/mix.mp4', 'v1', ?, ?, NULL)
                """,
                (t1, t2),
            )
            rows = [
                (1, 1, 1, 0.0, 2.0, 0.71, 'video', 'yolo', 10, now.isoformat()),
                (2, 1, 2, 3.0, 5.0, 0.68, 'video', 'yolo', 11, now.isoformat()),
                (3, 1, 1, 0.0, 2.0, 0.80, 'video', 'frigate', 12, now.isoformat()),
                (4, 1, 2, 3.0, 5.0, 0.78, 'video', 'frigate', 13, now.isoformat()),
                (5, 1, 3, 6.0, 8.0, 0.82, 'video', 'frigate', 20, now.isoformat()),
                (6, 1, 3, 8.0, 10.0, 0.83, 'video', 'frigate', 21, now.isoformat()),
                (7, 1, 3, 10.0, 12.0, 0.84, 'video', 'frigate', 22, now.isoformat()),
                (8, 1, 3, 12.0, 14.0, 0.85, 'video', 'frigate', 23, now.isoformat()),
            ]
            conn.executemany(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            conn.close()

            out = build_fusion_ab_report_from_db(
                db_path=db_path,
                days=14,
                min_yolo_share=0.30,
                min_yolo_share_bird_only=0.30,
                min_yolo_share_bird_only_warn=0.15,
                min_yolo_track_found_rate_warn=0.40,
                min_decision_trace_rows_warn=20,
                max_duplicate_video_groups=0,
                max_duplicate_detection_groups=0,
                max_generic_overlap_ratio=0.80,
                max_calendar_delta_ratio=5.0,
                calendar_compare_totals={
                    'encounters': 10,
                    'max_simultaneous': 12,
                    'delta': 2,
                },
            )
            self.assertFalse(out['gates']['yolo_share_ok'])
            self.assertTrue(out['gates']['yolo_share_bird_only_ok'])
            self.assertGreater(out['metrics']['yolo_bird_share_vs_frigate'], 0.30)
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_warning_gate_and_frigate_hotspots_are_reported(self):
        """Warning gate is independent from hard gates, and hotspots are emitted."""
        from ml_fusion_ab_report import build_fusion_ab_report_from_db

        db_path = _mk_db()
        now = datetime.now(timezone.utc)
        t1 = now.isoformat()
        t2 = (now + timedelta(seconds=20)).isoformat()
        try:
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE birdnet_fifo_event (
                  id INTEGER PRIMARY KEY,
                  ts_epoch REAL NOT NULL,
                  payload TEXT NOT NULL
                );
                """
            )
            conn.executemany(
                'INSERT INTO species (id, name) VALUES (?, ?)',
                [
                    (1, 'Great Tit'),
                    (2, 'Blue Tit'),
                    (3, 'Rodent'),
                ],
            )
            conn.execute(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (1, '/warn.mp4', 'v1', ?, ?, NULL)
                """,
                (t1, t2),
            )
            conn.executemany(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, 1, 1, 0.0, 2.0, 0.70, 'video', 'yolo', 10, now.isoformat()),
                    (2, 1, 1, 2.0, 4.0, 0.78, 'video', 'frigate', 20, now.isoformat()),
                    (3, 1, 2, 4.0, 6.0, 0.77, 'video', 'frigate', 21, now.isoformat()),
                    (4, 1, 3, 6.0, 8.0, 0.80, 'video', 'frigate', 22, now.isoformat()),
                ],
            )
            events = [
                (
                    1,
                    now.timestamp(),
                    '{"source":"frigate","camera":"cam-a","label":"bird","species":"great tit"}',
                ),
                (
                    2,
                    now.timestamp(),
                    '{"source":"frigate","camera":"cam-a","label":"bird","species":"blue tit"}',
                ),
                (
                    3,
                    now.timestamp(),
                    '{"source":"frigate","camera":"cam-b","label":"rodent","species":"rodent"}',
                ),
            ]
            conn.executemany(
                'INSERT INTO birdnet_fifo_event (id, ts_epoch, payload) VALUES (?, ?, ?)',
                events,
            )
            conn.commit()
            conn.close()

            out = build_fusion_ab_report_from_db(
                db_path=db_path,
                days=14,
                min_yolo_share=0.20,
                min_yolo_share_bird_only=0.20,
                min_yolo_share_bird_only_warn=0.40,
                min_yolo_track_found_rate_warn=0.40,
                min_decision_trace_rows_warn=20,
                max_duplicate_video_groups=0,
                max_duplicate_detection_groups=0,
                max_generic_overlap_ratio=0.80,
                max_calendar_delta_ratio=5.0,
                calendar_compare_totals={
                    'encounters': 10,
                    'max_simultaneous': 12,
                    'delta': 2,
                },
            )
            self.assertTrue(out['ok'])
            self.assertFalse(out['warning_gates']['yolo_share_bird_only_warn_ok'])
            self.assertTrue(any('yolo_bird_share_warn_low' in w for w in (out.get('warnings') or [])))
            hotspots = out['metrics']['frigate_hotspots']
            self.assertGreaterEqual(len(hotspots['by_camera']), 1)
            self.assertEqual(hotspots['by_camera'][0]['camera'], 'cam-a')
            self.assertGreaterEqual(hotspots['by_camera'][0]['count'], 2)
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_frigate_hotspots_fallback_to_decision_trace_activity(self):
        """When FIFO has no Frigate source rows, hotspots use decision_trace fallback."""
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
                    (1, 'Great Tit'),
                ],
            )
            conn.execute(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (1, '/fallback.mp4', 'v1', ?, ?, NULL)
                """,
                (t1, t2),
            )
            conn.execute(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1, 1, 1, 0.0, 2.0, 0.74, 'video', 'frigate', 10, now.isoformat()),
            )
            trace_payload = {
                'recording_context': {
                    'triggered_by': 'frigate',
                    'triggered_camera': 'forest',
                },
                'persisted_tracks': [
                    {
                        'primary_provider': 'frigate',
                        'species_name': 'Great Tit',
                    }
                ],
            }
            conn.execute(
                """
                INSERT INTO activity_log (id, type, created_at, data)
                VALUES (?, ?, ?, ?)
                """,
                (1, 'decision_trace', now.isoformat(), json.dumps(trace_payload)),
            )
            conn.commit()
            conn.close()

            out = build_fusion_ab_report_from_db(
                db_path=db_path,
                days=14,
                min_yolo_share=0.0,
                min_yolo_share_bird_only=0.0,
                min_yolo_share_bird_only_warn=0.0,
                min_yolo_track_found_rate_warn=0.40,
                min_decision_trace_rows_warn=20,
                max_duplicate_video_groups=0,
                max_duplicate_detection_groups=0,
                max_generic_overlap_ratio=1.0,
                max_calendar_delta_ratio=5.0,
                calendar_compare_totals={
                    'encounters': 1,
                    'max_simultaneous': 1,
                    'delta': 0,
                },
            )
            hotspots = out['metrics']['frigate_hotspots']
            self.assertGreaterEqual(len(hotspots['by_camera']), 1)
            self.assertEqual(hotspots['by_camera'][0]['camera'], 'forest')
            self.assertGreaterEqual(hotspots['by_camera'][0]['count'], 1)
            self.assertGreaterEqual(len(hotspots['by_label']), 1)
            self.assertEqual(hotspots['by_label'][0]['label'], 'great tit')
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_frigate_hotspots_ignore_person_like_labels(self):
        """Frigate hotspots should not be dominated by person/dog/cat traffic."""
        from ml_fusion_ab_report import build_fusion_ab_report_from_db

        db_path = _mk_db()
        now = datetime.now(timezone.utc)
        t1 = now.isoformat()
        t2 = (now + timedelta(seconds=20)).isoformat()
        try:
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE birdnet_fifo_event (
                  id INTEGER PRIMARY KEY,
                  ts_epoch REAL NOT NULL,
                  payload TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                INSERT INTO species (id, name) VALUES (1, 'Great Tit')
                """
            )
            conn.execute(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (1, '/hotspots.mp4', 'v1', ?, ?, NULL)
                """,
                (t1, t2),
            )
            conn.execute(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1, 1, 1, 0.0, 2.0, 0.74, 'video', 'frigate', 10, now.isoformat()),
            )
            events = [
                (
                    1,
                    now.timestamp(),
                    '{"source":"frigate","camera":"cam-a","label":"bird","species":"great tit"}',
                ),
                (
                    2,
                    now.timestamp(),
                    '{"source":"frigate","camera":"cam-a","label":"person","species":"person"}',
                ),
                (
                    3,
                    now.timestamp(),
                    '{"source":"frigate","camera":"cam-b","label":"dog","species":"dog"}',
                ),
            ]
            conn.executemany(
                'INSERT INTO birdnet_fifo_event (id, ts_epoch, payload) VALUES (?, ?, ?)',
                events,
            )
            conn.commit()
            conn.close()

            out = build_fusion_ab_report_from_db(
                db_path=db_path,
                days=14,
                min_yolo_share=0.0,
                min_yolo_share_bird_only=0.0,
                min_yolo_share_bird_only_warn=0.0,
                min_yolo_track_found_rate_warn=0.40,
                min_decision_trace_rows_warn=20,
                max_duplicate_video_groups=0,
                max_duplicate_detection_groups=0,
                max_generic_overlap_ratio=1.0,
                max_calendar_delta_ratio=5.0,
                calendar_compare_totals={
                    'encounters': 1,
                    'max_simultaneous': 1,
                    'delta': 0,
                },
            )
            hotspots = out['metrics']['frigate_hotspots']
            labels = {row['label'] for row in hotspots['by_label']}
            self.assertIn('bird', labels)
            self.assertNotIn('person', labels)
            self.assertNotIn('dog', labels)
            self.assertGreaterEqual(len(hotspots['by_camera']), 1)
            self.assertEqual(hotspots['by_camera'][0]['camera'], 'cam-a')
            self.assertEqual(hotspots['by_camera'][0]['count'], 1)
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_yolo_track_found_rate_and_camera_breakdown_are_reported(self):
        """Decision trace runtime_signals produce yolo_track stats and warning."""
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
                    (1, 'Great Tit'),
                ],
            )
            conn.execute(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (1, '/tracks.mp4', 'v1', ?, ?, NULL)
                """,
                (t1, t2),
            )
            conn.execute(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1, 1, 1, 0.0, 2.0, 0.74, 'video', 'frigate', 10, now.isoformat()),
            )
            traces = [
                (
                    1,
                    'decision_trace',
                    now.isoformat(),
                    json.dumps(
                        {
                            'recording_context': {
                                'triggered_camera': 'birdbox',
                                'runtime_signals': {
                                    'yolo_ran': True,
                                    'yolo_track_found': False,
                                },
                            }
                        }
                    ),
                ),
                (
                    2,
                    'decision_trace',
                    now.isoformat(),
                    json.dumps(
                        {
                            'recording_context': {
                                'triggered_camera': 'forest',
                                'runtime_signals': {
                                    'yolo_ran': True,
                                    'yolo_track_found': True,
                                },
                            }
                        }
                    ),
                ),
            ]
            conn.executemany(
                'INSERT INTO activity_log (id, type, created_at, data) VALUES (?, ?, ?, ?)',
                traces,
            )
            conn.commit()
            conn.close()

            out = build_fusion_ab_report_from_db(
                db_path=db_path,
                days=14,
                min_yolo_share=0.0,
                min_yolo_share_bird_only=0.0,
                min_yolo_share_bird_only_warn=0.0,
                min_yolo_track_found_rate_warn=0.75,
                min_decision_trace_rows_warn=20,
                max_duplicate_video_groups=0,
                max_duplicate_detection_groups=0,
                max_generic_overlap_ratio=1.0,
                max_calendar_delta_ratio=5.0,
                calendar_compare_totals={
                    'encounters': 1,
                    'max_simultaneous': 1,
                    'delta': 0,
                },
            )
            stats = out['metrics']['yolo_track_stats']
            self.assertEqual(stats['decision_trace_rows'], 2)
            self.assertEqual(stats['yolo_track_found_rows'], 1)
            self.assertAlmostEqual(stats['yolo_track_found_rate'], 0.5, places=6)
            self.assertGreaterEqual(len(stats['by_camera']), 2)
            camera_map = {row['camera']: row for row in stats['by_camera']}
            self.assertAlmostEqual(camera_map['birdbox']['yolo_track_found_rate'], 0.0, places=6)
            self.assertAlmostEqual(camera_map['forest']['yolo_track_found_rate'], 1.0, places=6)
            self.assertTrue(any('yolo_track_found_warn_low' in w for w in (out.get('warnings') or [])))
            self.assertTrue(any('decision_trace_sample_too_small' in w for w in (out.get('warnings') or [])))
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main()
