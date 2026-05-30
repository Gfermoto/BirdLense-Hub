"""Golden pack scenarios for Decision Engine contract (#533)."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
app_path = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.insert(0, src_path)
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from decision_maker import DecisionMaker  # noqa: E402
from recording_no_detection_log import log_no_detection_activity  # noqa: E402
from track_geometry import (  # noqa: E402
    StaticPinnedTrackConfig,
    static_pinned_track_reason,
)


def _track(
    *,
    start_time: float,
    end_time: float,
    detector_conf: float,
    classifier_species: str,
    classifier_conf: float,
    frames: list[dict],
) -> dict:
    return {
        "start_time": start_time,
        "end_time": end_time,
        "detector_events": [
            {"label": "Bird", "confidence": detector_conf, "t": start_time},
            {"label": "Bird", "confidence": detector_conf, "t": end_time},
        ],
        "classifier_events": [
            {
                "species_name": classifier_species,
                "confidence": classifier_conf,
                "detector_confidence": detector_conf,
                "combined_confidence": classifier_conf * detector_conf,
                "t": start_time,
            }
        ],
        "frames": frames,
        "best_frame_score": 7.0,
        "key_frames": frames[:1],
    }


class TestDecisionEngineGoldenPack(unittest.TestCase):
    def test_scenario_frigate_window_but_no_persist(self):
        api = MagicMock()
        log_no_detection_activity(
            api,
            track_count=3,
            mqtt_event_count=8,
            rejected_count=3,
            rejected_reason_counts={
                "rejected_short_track": 2,
                "rejected_static_pinned_track": 1,
            },
            video_path_for_api="data/recordings/golden/scenario_1.mp4",
            trigger_source="frigate",
            triggered_camera="Forest",
        )
        payload = api.activity_log.call_args.kwargs["data"]
        self.assertEqual(
            payload["reason_code"],
            "FUSION_NO_ACCEPTED_STATIC_PINNED",
        )
        self.assertEqual(payload["trigger_source"], "frigate")

    def test_scenario_sticky_crop_static_track_rejected(self):
        frames = [
            {"timestamp": float(i), "bbox": [0.42, 0.31, 0.51, 0.41]}
            for i in range(12)
        ]
        reason = static_pinned_track_reason(
            {"start_time": 0.0, "end_time": 10.0, "frames": frames},
            StaticPinnedTrackConfig(),
        )
        self.assertIsNotNone(reason)
        self.assertIn("rejected_static_pinned_track", str(reason))

    def test_scenario_misclass_short_track_has_traceable_reason(self):
        dm = DecisionMaker(min_track_duration=2.0)
        decisions = dm.get_decisions(
            {
                7: _track(
                    start_time=0.0,
                    end_time=0.7,
                    detector_conf=0.9,
                    classifier_species="Magpie",
                    classifier_conf=0.95,
                    frames=[{"t": 0.0, "bbox": [0.1, 0.1, 0.2, 0.2]}],
                )
            }
        )
        self.assertEqual(len(decisions), 1)
        row = decisions[0]
        self.assertEqual(row["decision_reason"], "rejected_short_track")
        self.assertEqual(row["reject_reason_code"], "insufficient_frames")
        self.assertEqual(row["outcome_bucket"], "rejected")


if __name__ == "__main__":
    unittest.main()
