"""RC2 async classify patch scaffold tests."""

from __future__ import annotations

import os
import sys
import time
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from async_classify_patch import (  # noqa: E402
    async_classify_patch_enabled,
    enqueue_async_classify_patch,
    leftover_tracks_for_async_patch,
    reset_async_classify_patch_for_tests,
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

    def test_enrich_named_leftover_via_api(self):
        class _Api:
            def __init__(self):
                self.calls = []

            def enrich_video_detection(self, video_id, detection_id, **kwargs):
                self.calls.append((video_id, detection_id, kwargs))
                return {"ok": True}

        cfg = _Cfg({"processor.async_classify_patch_enabled": True})
        api = _Api()
        n = enqueue_async_classify_patch(
            app_config=cfg,
            video_id=3,
            camera_id="Forest",
            video_path="data/y.mp4",
            decisions=[
                {
                    "track_id": 11,
                    "classify_skip_reason": "budget",
                    "patch_species_name": "Great Tit",
                    "confidence": 0.88,
                }
            ],
            track_map=[{"id": 55, "track_id": 11, "species_id": 1}],
            api=api,
        )
        self.assertEqual(n, 1)
        time.sleep(0.08)
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(api.calls[0][0], 3)
        self.assertEqual(api.calls[0][1], 55)
        self.assertEqual(api.calls[0][2]["species_name"], "Great Tit")
        reset_async_classify_patch_for_tests()


if __name__ == "__main__":
    unittest.main()
