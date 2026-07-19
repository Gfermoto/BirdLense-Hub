"""RC2 async classify patch + reclassify tests."""

from __future__ import annotations

import os
import sys
import time
import unittest
from types import SimpleNamespace

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from async_classify_patch import (  # noqa: E402
    async_classify_patch_enabled,
    enqueue_async_classify_patch,
    leftover_tracks_for_async_patch,
    reset_async_classify_patch_for_tests,
    snapshot_leftover_tracks,
)


class _Cfg:
    def __init__(self, d):
        self._d = d

    def get(self, key, default=None):
        return self._d.get(key, default)


class TestAsyncClassifyPatch(unittest.TestCase):
    def setUp(self):
        reset_async_classify_patch_for_tests()

    def test_disabled_by_default(self):
        self.assertFalse(async_classify_patch_enabled(_Cfg({})))
        n = enqueue_async_classify_patch(
            app_config=_Cfg({}),
            video_id=1,
            camera_id="Forest",
            video_path=None,
            decisions=[{"track_id": 1, "classify_skip_reason": "budget"}],
        )
        self.assertEqual(n, 0)

    def test_leftover_selection(self):
        rows = [
            {"track_id": 1, "classify_skip_reason": "budget"},
            {"track_id": 2, "classify_skip_reason": "unknown_abstain"},
            {"track_id": 3, "skip_reason": "timeout"},
        ]
        left = leftover_tracks_for_async_patch(rows)
        self.assertEqual({r["track_id"] for r in left}, {1, 3})

    def test_snapshot_leftover_tracks(self):
        tracks = {
            1: {"best_frame": "a", "classify_skip_reason": "budget", "classifier_events": [{"x": 1}]},
            2: {"best_frame": "b"},
        }
        snap = snapshot_leftover_tracks(
            tracks,
            [{"track_id": 1, "classify_skip_reason": "budget"}],
        )
        self.assertIn(1, snap)
        self.assertNotIn("classifier_events", snap[1])
        self.assertNotIn("classify_skip_reason", snap[1])
        self.assertEqual(snap[1]["best_frame"], "a")

    def test_enqueue_when_enabled(self):
        cfg = _Cfg({"processor.async_classify_patch_enabled": True})
        n = enqueue_async_classify_patch(
            app_config=cfg,
            video_id=9,
            camera_id="BirdBox",
            video_path="data/x.mp4",
            decisions=[{"track_id": 7, "classify_skip_reason": "deferred"}],
        )
        self.assertEqual(n, 1)
        time.sleep(0.05)
        reset_async_classify_patch_for_tests()

    def test_reclassify_then_enrich_named_leftover(self):
        class _Api:
            def __init__(self):
                self.calls = []

            def enrich_video_detection(self, video_id, detection_id, **kwargs):
                self.calls.append((video_id, detection_id, kwargs))
                return {"ok": True}

        class _Strategy:
            def _classify_crop(self, _crop):
                return SimpleNamespace(
                    species_name="Great Tit",
                    top1_confidence=0.88,
                    entropy=0.4,
                    top1_top2_margin=0.2,
                )

        cfg = _Cfg(
            {
                "processor.async_classify_patch_enabled": True,
                "processor.async_classify_patch_max_runtime_ms": 2000,
                "processor.classifier_defer_to_finalize": True,
                "processor.classifier_finalize_max_key_frames": 1,
                "processor.classifier_best_guess_min_confidence": 0.10,
            }
        )
        api = _Api()
        session_tracks = {
            11: {
                "detector_events": [{"label": "Bird", "confidence": 0.6}],
                "best_frame": object(),
                "best_frame_score": 2.0,
                "end_time": 1.0,
                "classify_skip_reason": "budget",
            }
        }
        n = enqueue_async_classify_patch(
            app_config=cfg,
            video_id=3,
            camera_id="Forest",
            video_path=None,
            decisions=[
                {
                    "track_id": 11,
                    "classify_skip_reason": "budget",
                    "species_name": "Bird",
                }
            ],
            track_map=[{"id": 55, "track_id": 11, "species_id": 1}],
            session_tracks=session_tracks,
            strategy=_Strategy(),
            api=api,
            sync=True,
        )
        self.assertEqual(n, 1)
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(api.calls[0][0], 3)
        self.assertEqual(api.calls[0][1], 55)
        self.assertEqual(api.calls[0][2]["species_name"], "Great Tit")
        reset_async_classify_patch_for_tests()


if __name__ == "__main__":
    unittest.main()
