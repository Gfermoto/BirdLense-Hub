"""Unit tests for runtime Ornimetrics welfare screening helpers."""

import os
import sys
import unittest
from unittest import mock

import numpy as np

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
_app_path = os.path.abspath(os.path.join(_current_dir, "../../"))
if _app_path not in sys.path:
    sys.path.insert(0, _app_path)


class TestWelfareRuntime(unittest.TestCase):
    def test_mahalanobis_distance_identity_cov(self):
        from welfare_runtime import _mahalanobis_distance

        emb = np.asarray([1.0, 2.0, 3.0], dtype=np.float32)
        mean = np.asarray([0.0, 0.0, 0.0], dtype=np.float32)
        inv_cov = np.eye(3, dtype=np.float32)
        self.assertAlmostEqual(_mahalanobis_distance(emb, mean, inv_cov), 14.0, places=5)

    def test_apply_runtime_welfare_flags_high_distance(self):
        from welfare_runtime import apply_runtime_welfare_metadata

        detections = [
            {
                "species_name": "Great Tit",
                "source": "video",
                "start_time": 1.0,
                "end_time": 2.5,
                "track_id": 7,
                "best_frame_score": 9.0,
                "best_frame": object(),
            }
        ]
        out = apply_runtime_welfare_metadata(
            detections,
            embed_crop=lambda _crop: np.ones(4, dtype=np.float32),
            score_embedding=lambda _emb: 120.0,
            model_name="ornimetrics_welfare",
            embed_dim=4,
            distance_review_threshold=75.0,
            max_detections=4,
            min_best_frame_score=5.0,
            flag_for_review=True,
            video_path="data/recordings/2026/05/02/235959/video.mp4",
        )
        row = out[0]
        self.assertEqual(row.get("welfare_model"), "ornimetrics_welfare")
        self.assertEqual(row.get("welfare_embed_dim"), 4)
        self.assertEqual(row.get("welfare_distance"), 120.0)
        self.assertTrue(row.get("welfare_needs_review"))
        self.assertTrue(row.get("classifier_needs_review"))
        self.assertEqual(row.get("review_reason"), "welfare_anomaly")

    def test_apply_runtime_welfare_skips_low_best_frame_score(self):
        from welfare_runtime import apply_runtime_welfare_metadata

        calls = {"n": 0}

        def _embed(_crop):
            calls["n"] += 1
            return np.ones(3, dtype=np.float32)

        detections = [
            {
                "species_name": "Sparrow",
                "source": "video",
                "best_frame_score": 1.0,
                "best_frame": object(),
            }
        ]
        apply_runtime_welfare_metadata(
            detections,
            embed_crop=_embed,
            score_embedding=lambda _emb: 10.0,
            model_name="ornimetrics_welfare",
            embed_dim=3,
            distance_review_threshold=5.0,
            max_detections=4,
            min_best_frame_score=5.0,
            flag_for_review=True,
            video_path="",
        )
        self.assertEqual(calls["n"], 0)

    def test_prewarm_runtime_welfare_model_uses_loader(self):
        import welfare_runtime as mod

        with mock.patch.object(mod, "_welfare_runtime_enabled", return_value=True), mock.patch.object(
            mod, "_cfg_bool", side_effect=lambda key, default: True if "preload_on_start" in key else default
        ), mock.patch.object(mod, "_ensure_model_state", return_value={"model_name": "ornimetrics_welfare"}):
            ok = mod.prewarm_runtime_welfare_model()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
