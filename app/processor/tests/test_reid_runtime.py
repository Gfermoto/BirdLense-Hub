"""Unit tests for runtime DINOv2 Re-ID enrichment helpers."""

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


class TestReidRuntime(unittest.TestCase):
    def test_apply_runtime_reid_sets_nickname_on_high_similarity(self):
        from reid_runtime import apply_runtime_reid_metadata

        detections = [
            {
                "species_name": "Great Tit",
                "source": "video",
                "start_time": 1.0,
                "end_time": 2.5,
                "track_id": 42,
                "best_frame_score": 9.1,
                "best_frame": object(),
            }
        ]

        out = apply_runtime_reid_metadata(
            detections,
            embed_crop=lambda _crop: np.asarray([1.0, 0.0], dtype=np.float32),
            load_candidates=lambda _species: [
                (np.asarray([0.99, 0.01], dtype=np.float32), "Синичка"),
            ],
            model_name="dinov2_vits14",
            similarity_threshold=0.8,
            max_detections=4,
            min_best_frame_score=5.5,
            flag_low_similarity_for_review=True,
            video_path="data/recordings/2026/05/02/235959/video.mp4",
        )

        row = out[0]
        self.assertEqual(row.get("individual_nickname"), "Синичка")
        self.assertEqual(row.get("reid_model"), "dinov2_vits14")
        self.assertEqual(row.get("reid_dim"), 2)
        self.assertTrue(isinstance(row.get("reid_embedding"), list))
        self.assertIn("runtime://data/recordings", str(row.get("reid_crop_key")))
        self.assertGreaterEqual(float(row.get("reid_similarity") or 0.0), 0.8)

    def test_apply_runtime_reid_respects_max_detections_cap(self):
        from reid_runtime import apply_runtime_reid_metadata

        calls = {"n": 0}

        def _embed(_crop):
            calls["n"] += 1
            return np.asarray([1.0, 0.0], dtype=np.float32)

        detections = []
        for i in range(5):
            detections.append(
                {
                    "species_name": "Sparrow",
                    "source": "video",
                    "start_time": float(i),
                    "end_time": float(i + 1),
                    "track_id": i,
                    "best_frame_score": 10.0,
                    "best_frame": object(),
                }
            )

        apply_runtime_reid_metadata(
            detections,
            embed_crop=_embed,
            load_candidates=lambda _species: [],
            model_name="dinov2_vits14",
            similarity_threshold=0.9,
            max_detections=2,
            min_best_frame_score=0.0,
            flag_low_similarity_for_review=True,
            video_path="data/recordings/x/video.mp4",
        )
        self.assertEqual(calls["n"], 2)

    def test_apply_runtime_reid_marks_review_when_no_match(self):
        from reid_runtime import apply_runtime_reid_metadata

        detections = [
            {
                "species_name": "Robin",
                "source": "video",
                "start_time": 1.0,
                "end_time": 2.0,
                "best_frame_score": 8.0,
                "best_frame": object(),
            }
        ]
        out = apply_runtime_reid_metadata(
            detections,
            embed_crop=lambda _crop: np.asarray([1.0, 0.0], dtype=np.float32),
            load_candidates=lambda _species: [
                (np.asarray([0.0, 1.0], dtype=np.float32), "OldNick"),
            ],
            model_name="dinov2_vits14",
            similarity_threshold=0.95,
            max_detections=3,
            min_best_frame_score=0.0,
            flag_low_similarity_for_review=True,
            video_path="data/recordings/y/video.mp4",
        )
        row = out[0]
        self.assertTrue(bool(row.get("classifier_needs_review")))
        self.assertEqual(row.get("review_reason"), "reid_no_match")

    def test_apply_runtime_reid_generates_nickname_when_no_match(self):
        from reid_runtime import apply_runtime_reid_metadata

        detections = [
            {
                "species_name": "Great Tit",
                "source": "video",
                "start_time": 3.0,
                "end_time": 4.0,
                "best_frame_score": 8.5,
                "best_frame": object(),
            }
        ]
        out = apply_runtime_reid_metadata(
            detections,
            embed_crop=lambda _crop: np.asarray([0.1, 0.9], dtype=np.float32),
            load_candidates=lambda _species: [],
            model_name="dinov2_vits14",
            similarity_threshold=0.95,
            max_detections=3,
            min_best_frame_score=0.0,
            flag_low_similarity_for_review=True,
            video_path="data/recordings/z/video.mp4",
        )
        nickname = str(out[0].get("individual_nickname") or "")
        self.assertTrue(nickname.startswith("great_tit_"))
        self.assertGreater(len(nickname), len("great_tit_"))

    def test_apply_runtime_reid_keeps_manual_nickname(self):
        from reid_runtime import apply_runtime_reid_metadata

        detections = [
            {
                "species_name": "Great Tit",
                "source": "video",
                "start_time": 5.0,
                "end_time": 6.0,
                "best_frame_score": 9.0,
                "best_frame": object(),
                "individual_nickname": "Рыжик",
            }
        ]
        out = apply_runtime_reid_metadata(
            detections,
            embed_crop=lambda _crop: np.asarray([0.5, 0.5], dtype=np.float32),
            load_candidates=lambda _species: [],
            model_name="dinov2_vits14",
            similarity_threshold=0.95,
            max_detections=3,
            min_best_frame_score=0.0,
            flag_low_similarity_for_review=True,
            video_path="data/recordings/k/video.mp4",
        )
        self.assertEqual(out[0].get("individual_nickname"), "Рыжик")

    def test_prewarm_runtime_reid_model_uses_loader(self):
        import reid_runtime as mod

        with (
            mock.patch.object(mod, "_reid_runtime_enabled", return_value=True),
            mock.patch.object(mod, "_cfg_bool", return_value=True),
            mock.patch.object(mod, "_ensure_model_state", return_value={"model": object()}),
            mock.patch.object(mod, "observe_timing") as m_obs,
        ):
            ok = mod.prewarm_runtime_reid_model()
        self.assertTrue(ok)
        self.assertTrue(m_obs.called)


if __name__ == "__main__":
    unittest.main()
