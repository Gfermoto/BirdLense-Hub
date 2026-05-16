"""SQLite decision_trace -> active-learning pool JSONL (#369)."""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

_REPO_ROOT = next(
    (p for p in (Path(__file__).resolve().parents[3], Path('/workspace')) if (p / 'scripts').exists()),
    Path(__file__).resolve().parents[3],
)
_AL_DIR = _REPO_ROOT / "scripts" / "active_learning"
if str(_AL_DIR) not in sys.path:
    sys.path.insert(0, str(_AL_DIR))


def _load_module():
    path = _AL_DIR / "export_pool_from_sqlite.py"
    spec = importlib.util.spec_from_file_location("export_pool_from_sqlite", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["export_pool_from_sqlite"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestActiveLearningExportPoolFromSqlite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_export_needs_review_rows(self):
        tmp = Path(self._testMethodName + ".db")
        out = Path(self._testMethodName + ".jsonl")
        try:
            conn = sqlite3.connect(tmp)
            conn.execute("CREATE TABLE activity_log (id INTEGER PRIMARY KEY, type TEXT, created_at TEXT, data TEXT)")
            trace = {
                "video_id": 42,
                "persisted_tracks": [
                    {
                        "track_id": 7,
                        "species_name": "Robin",
                        "detector_confidence": 0.9,
                        "classifier_entropy": 1.1,
                        "classifier_top1_top2_margin": 0.03,
                        "classifier_needs_review": True,
                        "persisted_to_clip": True,
                    },
                    {
                        "track_id": 8,
                        "species_name": "Robin",
                        "classifier_needs_review": False,
                    },
                ],
                "rejected_tracks": [],
            }
            conn.execute(
                "INSERT INTO activity_log (type, created_at, data) VALUES (?, ?, ?)",
                ("decision_trace", "2026-04-28T00:00:00Z", json.dumps(trace)),
            )
            conn.commit()
            conn.close()
            args = SimpleNamespace(
                db=str(tmp),
                output=str(out),
                limit=100,
                since_id=0,
                video_id=None,
                needs_review_only=True,
                entropy_ge=None,
                margin_le=None,
                seed=123,
                model_version="test_model",
                dedupe=True,
            )
            rc = self.mod.export_pool_from_sqlite(args)
            self.assertEqual(rc, 0)
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["video_id"], "42")
            self.assertEqual(rows[0]["track_id"], 7)
            self.assertTrue(rows[0]["classifier_needs_review"])
        finally:
            tmp.unlink(missing_ok=True)
            out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
