"""Synthetic tests for app/scripts/merge_duplicate_detections.py."""

import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    mod_path = repo_root / 'app' / 'scripts' / 'merge_duplicate_detections.py'
    spec = importlib.util.spec_from_file_location(
        'merge_duplicate_detections',
        str(mod_path),
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_db() -> str:
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE species_visit (
          id INTEGER PRIMARY KEY,
          species_id INTEGER
        );
        CREATE TABLE video_species (
          id INTEGER PRIMARY KEY,
          video_id INTEGER,
          species_id INTEGER,
          start_time REAL,
          end_time REAL,
          confidence REAL,
          frames TEXT,
          track_id INTEGER,
          species_visit_id INTEGER,
          source TEXT,
          detection_provider TEXT,
          individual_nickname TEXT,
          manually_corrected INTEGER,
          classifier_needs_review INTEGER,
          review_reason TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return path


class TestMergeDuplicateDetections(unittest.TestCase):
    """Data-preserving merge checks for duplicate video detections."""

    def test_merge_preserves_nickname_and_manual_flags(self):
        """Merged row keeps nickname/provider/flags from grouped detections."""
        mod = _load_module()
        db_path = _mk_db()
        try:
            conn = sqlite3.connect(db_path)
            conn.executemany(
                'INSERT INTO species_visit (id, species_id) VALUES (?, ?)',
                [(10, 1), (11, 1)],
            )
            conn.executemany(
                """
                INSERT INTO video_species
                  (id, video_id, species_id, start_time, end_time, confidence,
                   frames, track_id, species_visit_id, source,
                   detection_provider, individual_nickname,
                   manually_corrected, classifier_needs_review, review_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        1, 100, 1, 2.0, 4.0, 0.91, '[]', None, None,
                        'video', None, None, 0, 0, None,
                    ),
                    (
                        2, 100, 1, 1.0, 6.0, 0.80, '[]', 77, 10,
                        'video', 'yolo', 'Nova', 1, 1,
                        'classifier_uncertainty',
                    ),
                    (
                        3, 100, 1, 0.5, 7.0, 0.70, '[]', None, 11,
                        'video', 'frigate', '', 0, 0, None,
                    ),
                ],
            )
            conn.commit()
            conn.close()

            old_db_path = mod.DB_PATH
            mod.DB_PATH = db_path
            try:
                mod.main()
            finally:
                mod.DB_PATH = old_db_path

            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                """
                SELECT id, start_time, end_time, confidence,
                       track_id, species_visit_id, detection_provider,
                       individual_nickname, manually_corrected,
                       classifier_needs_review, review_reason
                FROM video_species
                WHERE video_id=100 AND species_id=1
                ORDER BY id
                """
            ).fetchall()
            conn.close()

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row[0], 1)
            self.assertEqual(row[1], 0.5)
            self.assertEqual(row[2], 7.0)
            self.assertEqual(row[3], 0.91)
            self.assertEqual(row[4], 77)
            self.assertEqual(row[5], 10)
            self.assertEqual(row[6], 'yolo')
            self.assertEqual(row[7], 'Nova')
            self.assertEqual(row[8], 1)
            self.assertEqual(row[9], 1)
            self.assertEqual(row[10], 'classifier_uncertainty')
        finally:
            try:
                os.unlink(db_path)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main()
