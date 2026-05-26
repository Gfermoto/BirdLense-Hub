"""SOTA-11: unified tracking policy parity between Live and Regen."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from tracking_policy import build_unified_tracking_policy, unified_with_live_pipeline


class _Cfg(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def _base_cfg(**extra):
    cfg = _Cfg(
        {
            "processor.min_track_duration": 0.6,
            "processor.track_regen_min_track_duration": 0.05,
            "processor.min_confidence_to_process": 0.4,
            "processor.track_regen_min_confidence_to_process": 0.12,
            "processor.track_regen_match_live_pipeline": True,
            "processor.track_regen_ignore_regional_species": True,
            "processor.regional_species": ["Cardinal"],
            "processor.iou_id_fallback_live_enabled": True,
            "processor.iou_id_fallback_live_match_threshold": 0.20,
            "processor.track_regen_iou_id_fallback": True,
            "processor.track_regen_iou_match_threshold": 0.22,
            "processor.track_regen_binary_only": True,
            "processor.tracker": "bytetrack.yaml",
            "processor.detection_strategy": "two_stage",
            "processor.min_center_dist": 0.1,
            "detection.min_confidence_to_store": 0.30,
        }
    )
    cfg.update(extra)
    return cfg


class TestUnifiedTrackingPolicy(unittest.TestCase):
    def test_unified_regen_matches_live_thresholds(self):
        cfg = _base_cfg()
        live = build_unified_tracking_policy(cfg, mode="live", source_fps=7.0, frame_step=1)
        regen = build_unified_tracking_policy(
            cfg, mode="regen", source_fps=7.0, frame_step=6
        )
        self.assertTrue(regen.unified_with_live)
        self.assertEqual(live.min_track_duration, regen.min_track_duration)
        self.assertEqual(live.min_confidence_to_process, regen.min_confidence_to_process)
        self.assertEqual(live.iou_id_fallback, regen.iou_id_fallback)
        self.assertEqual(live.iou_match_threshold, regen.iou_match_threshold)
        self.assertEqual(live.geometry_mode, "live")
        self.assertEqual(regen.geometry_mode, "live")
        self.assertFalse(regen.binary_only)
        self.assertFalse(regen.use_regen_direct_track_call)

    def test_legacy_regen_diverges_when_match_live_false(self):
        cfg = _base_cfg(
            **{
                "processor.track_regen_match_live_pipeline": False,
            }
        )
        regen = build_unified_tracking_policy(
            cfg, mode="regen", source_fps=10.0, frame_step=2
        )
        self.assertFalse(regen.unified_with_live)
        self.assertEqual(regen.min_track_duration, 0.05)
        self.assertEqual(regen.geometry_mode, "regen")
        self.assertTrue(regen.use_regen_direct_track_call)

    def test_effective_fps_from_frame_step(self):
        cfg = _base_cfg()
        pol = build_unified_tracking_policy(
            cfg, mode="regen", source_fps=12.0, frame_step=3
        )
        self.assertAlmostEqual(pol.effective_stream_fps(), 4.0)

    def test_unified_default_true(self):
        cfg = _Cfg({"processor.track_regen_match_live_pipeline": None})
        self.assertTrue(unified_with_live_pipeline(cfg))


class TestLiveRegenParityPolicy(unittest.TestCase):
    """Policy-level parity: same tracker path settings at frame_step=1."""

    def test_live_regen_parity_at_full_fps(self):
        cfg = _base_cfg()
        live = build_unified_tracking_policy(cfg, mode="live", source_fps=8.0, frame_step=1)
        regen = build_unified_tracking_policy(
            cfg, mode="regen", source_fps=8.0, frame_step=1
        )
        self.assertEqual(
            live.session_context()["tracking_unified_with_live"],
            regen.session_context()["tracking_unified_with_live"],
        )
        self.assertEqual(
            live.resolve_tracker_path("bytetrack.yaml"),
            regen.resolve_tracker_path("bytetrack.yaml"),
        )
        self.assertEqual(live.geometry_mode_for_frame(), regen.geometry_mode_for_frame())


if __name__ == "__main__":
    unittest.main()
