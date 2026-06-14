"""Regen must apply per-camera role/scoring overrides like live recording."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from threshold_resolution import (  # noqa: E402
    _recording_path_match_candidates,
    resolve_camera_id_for_recording_path,
)
from tracking_policy import UnifiedTrackingPolicy, apply_policy_profile_overrides
from tracking_service import TrackingService


class TestRecordingPathCameraResolve(unittest.TestCase):
    def test_path_suffix_candidates(self):
        cands = _recording_path_match_candidates(
            "/app/data/recordings/2026/06/11/170412/video.mp4",
        )
        self.assertIn("2026/06/11/170412/video.mp4", cands)
        self.assertIn("data/recordings/2026/06/11/170412/video.mp4", cands)
        self.assertIn("video.mp4", cands)

    def test_sqlite_lookup_by_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "birdlense.db")
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE video (id INTEGER PRIMARY KEY, video_path TEXT, camera_id TEXT)"
            )
            conn.execute(
                "INSERT INTO video (video_path, camera_id) VALUES (?, ?)",
                ("data/recordings/2026/06/11/170412/video.mp4", "Forest"),
            )
            conn.commit()
            conn.close()

            class _Cfg:
                def get(self, key, default=None):
                    return default

            cam = resolve_camera_id_for_recording_path(
                _Cfg(),
                "/app/data/recordings/2026/06/11/170412/video.mp4",
                db_path=db,
            )
            self.assertEqual(cam, "Forest")


class TestTrackingServiceCameraOverrides(unittest.TestCase):
    def test_process_video_passes_camera_overrides_to_run(self):
        fp = MagicMock()
        fp.run.return_value = False
        fp.tracks = {}
        fp.last_run_stats = {}
        dm = MagicMock()
        policy = MagicMock()
        policy.skip_light_gate = True
        policy.source_fps = 7.0
        policy.frame_step = 1
        policy.geometry_mode_for_frame.return_value = "regen"
        policy.session_context.return_value = {}

        svc = TrackingService(fp, dm, policy, runtime_cfg={})
        overrides = {"min_confidence_binary_bird": 0.05, "scoring_static_phantom_reject_enabled": False}

        with patch("tracking_service.os.path.isfile", return_value=True), patch(
            "tracking_service.cv2.VideoCapture"
        ) as cap_cls, patch(
            "tracking_service.prepare_detector_pipeline_frame",
            return_value=(MagicMock(), None, None, None),
        ), patch(
            "threshold_resolution.resolve_camera_id_for_recording_path",
            return_value="Forest",
        ), patch(
            "threshold_resolution.build_camera_processor_overrides",
            return_value=overrides,
        ):
            cap = MagicMock()
            cap.isOpened.return_value = True
            cap.read.side_effect = [(True, MagicMock()), (False, None)]
            cap.get.return_value = 0.0
            cap_cls.return_value = cap

            svc.process_video("/tmp/fake/video.mp4", frame_step=1)

        fp.run.assert_called_once()
        _args, kwargs = fp.run.call_args
        self.assertEqual(kwargs.get("camera_overrides"), overrides)


class TestApplyPolicyProfileOverrides(unittest.TestCase):
    def test_regen_does_not_raise_above_role_preset(self):
        policy = UnifiedTrackingPolicy(
            mode="regen",
            unified_with_live=False,
            stream_fps=7.0,
            source_fps=7.0,
            frame_step=1,
            geometry_mode="regen",
            for_track_regen=True,
            base_tracker="bytetrack.yaml",
            min_track_duration=0.05,
            min_confidence_to_process=None,
            min_confidence_to_store=None,
            min_confidence_binary_override=0.21,
            min_confidence_binary_bird_override=0.22,
        )
        out = apply_policy_profile_overrides(
            {"min_confidence_binary": 0.06, "min_confidence_binary_bird": 0.05},
            policy,
        )
        self.assertEqual(out["min_confidence_binary"], 0.06)
        self.assertEqual(out["min_confidence_binary_bird"], 0.05)


if __name__ == "__main__":
    unittest.main()
