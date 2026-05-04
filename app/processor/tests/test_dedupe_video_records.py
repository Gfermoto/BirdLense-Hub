"""Synthetic tests for scripts/dedupe_video_records.py."""

import os
import sqlite3
import sys
import tempfile
import unittest

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
              individual_nickname TEXT
            );
            CREATE TABLE video_bird_food_association (
              video_id INTEGER,
              birdfood_id INTEGER,
              PRIMARY KEY (video_id, birdfood_id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


class TestDedupeVideoRecords(unittest.TestCase):
    """Video-level dedupe and FK remap."""

    def test_dedupe_merges_fk_rows_and_removes_duplicate_video(self):
        """Dedupe keeps one video and moves dependent rows to it."""
        from dedupe_video_records import dedupe_video_records

        db_path = _mk_db()
        try:
            conn = sqlite3.connect(db_path)
            conn.executemany(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                [
                    (
                        1, '/same.mp4', 'v1',
                        '2026-05-01T00:00:00+00:00',
                        '2026-05-01T00:00:10+00:00',
                    ),
                    (
                        2, '/same.mp4', 'v1',
                        '2026-05-01T00:00:00+00:00',
                        '2026-05-01T00:00:10+00:00',
                    ),
                ],
            )
            conn.executemany(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, individual_nickname)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, 1, 10, 0.0, 5.0, 0.8, 'video', 'yolo', 11, 'Alpha'),
                    (2, 2, 10, 0.0, 5.0, 0.8, 'video', 'yolo', 11, 'Alpha'),
                ],
            )
            conn.executemany(
                'INSERT INTO video_bird_food_association '
                '(video_id, birdfood_id) VALUES (?, ?)',
                [
                    (1, 100),
                    (2, 100),
                    (2, 200),
                ],
            )
            conn.commit()
            conn.close()

            out = dedupe_video_records(db_path=db_path, dry_run=False)
            self.assertEqual(out['duplicate_groups'], 1)
            self.assertEqual(out['deleted_video_rows'], 1)
            self.assertGreaterEqual(out['deduped_video_species_rows'], 1)

            conn = sqlite3.connect(db_path)
            videos = conn.execute('SELECT id FROM video ORDER BY id').fetchall()
            self.assertEqual(videos, [(1,)])
            vs = conn.execute(
                'SELECT video_id, COUNT(*) FROM video_species GROUP BY video_id'
            ).fetchall()
            self.assertEqual(vs, [(1, 1)])
            bf = conn.execute(
                'SELECT video_id, birdfood_id '
                'FROM video_bird_food_association ORDER BY birdfood_id'
            ).fetchall()
            self.assertEqual(bf, [(1, 100), (1, 200)])
            conn.close()
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass

    def test_dedupe_keeps_rows_with_different_nickname(self):
        """Rows that differ only by nickname must not be collapsed."""
        from dedupe_video_records import dedupe_video_records

        db_path = _mk_db()
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                INSERT INTO video
                  (id, video_path, processor_version, start_time, end_time, deleted_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    1, '/single.mp4', 'v1',
                    '2026-05-01T00:00:00+00:00',
                    '2026-05-01T00:00:10+00:00',
                ),
            )
            conn.executemany(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence, source, detection_provider, track_id, individual_nickname)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, 1, 10, 0.0, 5.0, 0.8, 'video', 'yolo', 11, 'Alpha'),
                    (2, 1, 10, 0.0, 5.0, 0.8, 'video', 'yolo', 11, 'Beta'),
                ],
            )
            conn.commit()
            conn.close()

            out = dedupe_video_records(db_path=db_path, dry_run=False)
            self.assertEqual(out['duplicate_groups'], 0)
            self.assertEqual(out['deduped_video_species_rows'], 0)

            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                'SELECT individual_nickname FROM video_species ORDER BY id'
            ).fetchall()
            self.assertEqual(rows, [('Alpha',), ('Beta',)])
            conn.close()
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main()
