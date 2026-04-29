"""Import Re-ID embedding JSONL into SQLite sidecar table (#374)."""

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / "scripts" / "reid" / "import_embeddings_sqlite.py"
    spec = importlib.util.spec_from_file_location("import_embeddings_sqlite", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["import_embeddings_sqlite"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestReidImportEmbeddingsSqlite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_import_embeddings_with_manifest_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            db = base / "birdlense.db"
            img = base / "crop.jpg"
            img.write_bytes(b"jpeg")
            jsonl = base / "embed.jsonl"
            manifest = base / "manifest.jsonl"
            jsonl.write_text(
                json.dumps(
                    {
                        "path": str(img),
                        "model": "dinov2_vits14",
                        "dim": 3,
                        "embedding": [0.1, 0.2, 0.3],
                    },
                )
                + "\n",
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "crop_path": str(img),
                        "video_species_id": 11,
                        "video_id": 22,
                        "species_id": 33,
                        "track_id": 44,
                        "species_name": "Robin",
                    },
                )
                + "\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                db=str(db),
                jsonl=str(jsonl),
                manifest=str(manifest),
            )
            rc = self.mod.import_embeddings(args)
            self.assertEqual(rc, 0)
            conn = sqlite3.connect(db)
            row = conn.execute(
                "SELECT video_species_id, video_id, species_id, track_id, model, dim, species_name "
                "FROM reid_embedding",
            ).fetchone()
            conn.close()
            self.assertEqual(row, (11, 22, 33, 44, "dinov2_vits14", 3, "Robin"))


if __name__ == "__main__":
    unittest.main()
