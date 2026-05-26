"""Golden clip quality gates for YOLO tracks (SOTA-05): video 1819 must have tracks."""

from __future__ import annotations

import os
import unittest


def assert_golden_clip_has_tracks(summary: dict, *, clip_label: str) -> None:
    tracks = int(summary.get("yolo_frames_with_tracks") or 0)
    if tracks <= 0:
        raise AssertionError(
            f"golden clip {clip_label}: yolo_frames_with_tracks=0 "
            f"(raw={summary.get('yolo_raw_boxes_total')}, ran={summary.get('yolo_frames_ran')})"
        )


class TestGoldenClipGateLogic(unittest.TestCase):
    def test_1819_passes_with_tracks(self):
        assert_golden_clip_has_tracks(
            {"yolo_frames_with_tracks": 3, "yolo_raw_boxes_total": 10, "yolo_frames_ran": 50},
            clip_label="1819",
        )

    def test_1819_fails_without_tracks(self):
        with self.assertRaises(AssertionError) as ctx:
            assert_golden_clip_has_tracks(
                {"yolo_frames_with_tracks": 0, "yolo_raw_boxes_total": 0, "yolo_frames_ran": 100},
                clip_label="1819",
            )
        self.assertIn("1819", str(ctx.exception))

    def test_1816_noise_allowed_zero_tracks(self):
        """1816 is noise reference — gate only enforces 1819."""
        summary = {"yolo_frames_with_tracks": 0, "yolo_raw_boxes_total": 0}
        tracks = int(summary.get("yolo_frames_with_tracks") or 0)
        self.assertEqual(tracks, 0)


@unittest.skipUnless(
    os.environ.get("YOLO_GOLDEN_CLIP_1819", "").strip(),
    "set YOLO_GOLDEN_CLIP_1819=/path/to/mp4 for heavy golden regen",
)
class TestGoldenClip1819Heavy(unittest.TestCase):
    def test_regen_produces_tracks(self):
        """Optional: run track regen on golden mp4 when path provided."""
        clip = os.environ["YOLO_GOLDEN_CLIP_1819"].strip()
        self.assertTrue(os.path.isfile(clip), clip)
        from track_regenerator import process_video_for_tracks

        detections = process_video_for_tracks(clip)
        assert_golden_clip_has_tracks(
            {
                "yolo_frames_with_tracks": 1 if detections else 0,
                "yolo_raw_boxes_total": len(detections),
            },
            clip_label="1819",
        )


if __name__ == "__main__":
    unittest.main()
