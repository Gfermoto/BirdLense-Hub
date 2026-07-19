"""RC4 concrete recognition adapters."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from recognition_adapters import (  # noqa: E402
    FrigateSpeciesHint,
    HubSpeciesAuthority,
    HubYoloBoxProvider,
    MotionDetectorTriggerSource,
    OpenCvTriggerSource,
    default_hub_stack,
    resolve_trigger_from_motion,
    summarize_recognition_stack,
)
from recognition_protocols import (  # noqa: E402
    BoxProvider,
    SpeciesAuthority,
    SpeciesHint,
    TriggerSource,
)


class TestRecognitionAdapters(unittest.TestCase):
    def test_protocol_satisfaction(self):
        stack = default_hub_stack(
            tracks={1: {"best_bbox": [0, 0, 1, 1], "best_frame_score": 1.2}},
            frigate_hints=[{"species_name": "Bird", "camera_id": "Forest"}],
        )
        self.assertIsInstance(stack["trigger"], TriggerSource)
        self.assertIsInstance(stack["boxes"], BoxProvider)
        self.assertIsInstance(stack["hints"], SpeciesHint)
        self.assertIsInstance(stack["authority"], SpeciesAuthority)

    def test_yolo_boxes(self):
        boxes = HubYoloBoxProvider({7: {"bbox": [1, 2, 3, 4], "confidence": 0.5}})
        out = boxes.boxes_for_window(start_time=None, end_time=None)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["track_id"], 7)

    def test_frigate_hint_camera_filter(self):
        hints = FrigateSpeciesHint(
            [
                {"species_name": "A", "camera_id": "Forest"},
                {"species_name": "B", "camera_id": "BirdBox"},
            ]
        )
        forest = hints.hints_for_window(start_time=None, end_time=None, camera_id="Forest")
        self.assertEqual([h["species_name"] for h in forest], ["A"])

    def test_opencv_trigger_idle(self):
        self.assertIsNone(OpenCvTriggerSource().poll())

    def test_hub_authority_rejects_generic(self):
        auth = HubSpeciesAuthority()
        self.assertFalse(auth.may_accept_named({"species_name": "Bird", "detection_provider": "yolo"}))


    def test_summarize_recognition_stack(self):
        blob = summarize_recognition_stack(
            tracks={1: {"bbox": [0, 0, 1, 1]}},
            mqtt_events=[],
            trigger_source="opencv",
            app_config=None,
        )
        self.assertEqual(blob["schema"], "recognition_stack@v1")
        self.assertEqual(blob["trigger"], "opencv")
        self.assertGreaterEqual(blob["box_count"], 1)
        self.assertTrue(blob["hub_is_species_authority"])

    def test_motion_detector_trigger_source(self):
        class _Md:
            def get_triggered_by(self):
                return "frigate"

            def get_triggered_camera(self):
                return "Forest"

        src = MotionDetectorTriggerSource(_Md())
        self.assertIsInstance(src, TriggerSource)
        ev = src.poll()
        self.assertEqual(ev["trigger_source"], "frigate")
        self.assertEqual(ev["camera_id"], "Forest")
        name, ev2 = resolve_trigger_from_motion(_Md())
        self.assertEqual(name, "frigate")
        self.assertEqual(ev2["camera_id"], "Forest")


if __name__ == "__main__":
    unittest.main()
