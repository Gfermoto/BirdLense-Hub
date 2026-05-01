"""Tests for action execution scripts (#379/#392)."""
# flake8: noqa

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = next(
    (
        p
        for p in (Path(__file__).resolve().parents[3], Path("/workspace"))
        if (p / "scripts").exists()
    ),
    Path(__file__).resolve().parents[3],
)


def _load_module(rel_path: str, module_name: str):
    path = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestActionExecutionScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_mod = _load_module(
            "scripts/action/export_action_seed_dataset.py",
            "export_action_seed_dataset",
        )
        cls.kappa_mod = _load_module(
            "scripts/action/compute_action_agreement.py",
            "compute_action_agreement",
        )
        cls.bench_mod = _load_module(
            "scripts/action/benchmark_action_candidates.py",
            "benchmark_action_candidates",
        )
        cls.calib_mod = _load_module(
            "scripts/action/prepare_action_calibration_pack.py",
            "prepare_action_calibration_pack",
        )

    def test_export_action_seed_dataset(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            db_path = base / "birdlense.db"
            out_jsonl = base / "seed.jsonl"
            out_manifest = base / "seed_manifest.json"

            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE video (
                    id INTEGER PRIMARY KEY,
                    scales_weight_delta_kg REAL,
                    video_path TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE video_species (
                    id INTEGER PRIMARY KEY,
                    video_id INTEGER,
                    track_id INTEGER,
                    start_time REAL,
                    end_time REAL
                )
                """
            )
            conn.execute(
                "INSERT INTO video (id, scales_weight_delta_kg, video_path) VALUES (1, 0.02, 'cam-a/clip-1.mp4')"
            )
            conn.execute(
                "INSERT INTO video_species (id, video_id, track_id, start_time, end_time) VALUES (1, 1, 10, 1.0, 2.0)"
            )
            conn.execute(
                "INSERT INTO video_species (id, video_id, track_id, start_time, end_time) VALUES (2, 1, 10, 2.5, 4.0)"
            )
            conn.commit()
            conn.close()

            summary = self.seed_mod.export_seed_rows(
                db_path=db_path,
                output_jsonl=out_jsonl,
                manifest_json=out_manifest,
                limit_videos=10,
                boundary_ms=300,
                min_track_duration_ms=300,
                min_tracks=1,
                min_weight_delta_kg=0.001,
                require_weight_delta=False,
                annotator_id="bootstrap_weak_label",
                video_ids=[],
            )
            self.assertEqual(summary["video_count"], 1)
            self.assertGreaterEqual(summary["row_count"], 3)
            rows = [json.loads(ln) for ln in out_jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            labels = sorted(r["action_label"] for r in rows)
            self.assertIn("arrival", labels)
            self.assertIn("departure", labels)
            self.assertIn("possible_feeding", labels)
            self.assertTrue(out_manifest.exists())

    def test_compute_action_agreement(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            ann_a = base / "a.jsonl"
            ann_b = base / "b.jsonl"
            ann_a.write_text(
                "\n".join(
                    [
                        json.dumps({"segment_uid": "s1", "action_label": "arrival"}),
                        json.dumps({"segment_uid": "s2", "action_label": "departure"}),
                        json.dumps({"segment_uid": "s3", "action_label": "possible_feeding"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            ann_b.write_text(
                "\n".join(
                    [
                        json.dumps({"segment_uid": "s1", "action_label": "arrival"}),
                        json.dumps({"segment_uid": "s2", "action_label": "departure"}),
                        json.dumps({"segment_uid": "s3", "action_label": "departure"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            ok, report = self.kappa_mod.compute_report(
                annotator_a_jsonl=ann_a,
                annotator_b_jsonl=ann_b,
                min_kappa=0.2,
                max_disagreements=10,
            )
            self.assertTrue(ok)
            self.assertGreater(report["kappa"], 0.2)
            self.assertEqual(report["coverage"]["overlap_count"], 3)

    def test_benchmark_action_candidates(self):
        gt = [
            {"video_id": 1, "action_label": "arrival", "time_offset": 1.0},
            {"video_id": 1, "action_label": "departure", "time_offset": 5.0},
        ]
        pred = [
            {"video_id": 1, "label": "arrival", "time_offset": 1.2, "model_id": "m1"},
            {"video_id": 1, "label": "departure", "time_offset": 5.1, "model_id": "m1"},
            {"video_id": 1, "label": "arrival", "time_offset": 8.0, "model_id": "m1"},
            {"video_id": 1, "label": "arrival", "time_offset": 3.0, "model_id": "m2"},
        ]
        report = self.bench_mod.benchmark_candidates(
            ground_truth_rows=gt,
            prediction_rows=pred,
            tolerance_sec=1.5,
        )
        self.assertEqual(report["best_model_id"], "m1")
        models = {m["model_id"]: m for m in report["models"]}
        self.assertEqual(models["m1"]["tp"], 2)
        self.assertEqual(models["m1"]["fp"], 1)
        self.assertEqual(models["m2"]["tp"], 0)

    def test_prepare_action_calibration_pack(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            seed = base / "seed.jsonl"
            outdir = base / "calib"
            rows = []
            for vid in range(1, 6):
                rows.append(
                    {
                        "segment_uid": f"v{vid}:arrival",
                        "video_id": vid,
                        "track_id": 1,
                        "camera_id": "cam-1",
                        "action_label": "arrival",
                        "t_start_ms": 0,
                        "t_end_ms": 300,
                        "created_at_utc": "2026-05-01T00:00:00Z",
                    }
                )
                rows.append(
                    {
                        "segment_uid": f"v{vid}:departure",
                        "video_id": vid,
                        "track_id": 1,
                        "camera_id": "cam-1",
                        "action_label": "departure",
                        "t_start_ms": 700,
                        "t_end_ms": 1000,
                        "created_at_utc": "2026-05-01T00:00:00Z",
                    }
                )
            seed.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n",
                encoding="utf-8",
            )
            summary = self.calib_mod.prepare_pack(
                seed_jsonl=seed,
                output_dir=outdir,
                max_videos=3,
                max_segments_per_video=2,
                annotator_a="a",
                annotator_b="b",
            )
            self.assertEqual(summary["subset_videos"], 3)
            self.assertEqual(summary["subset_rows"], 6)
            self.assertTrue((outdir / "action_calibration_subset.jsonl").exists())
            self.assertTrue((outdir / "action_calibration_annotator_a.jsonl").exists())
            self.assertTrue((outdir / "action_calibration_annotator_b.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
