"""Track-first persist contract tests."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from track_first_contract import (  # noqa: E402
    apply_track_first_persist_gate,
    count_ingestible_track_rows,
    has_ingestible_track_rows,
)


class TestTrackFirstContract(unittest.TestCase):
    def test_drops_video_row_without_frames(self):
        rows = [
            {
                "source": "video",
                "detection_provider": "yolo",
                "species_name": "Great Tit",
                "frames": [],
            }
        ]
        kept, rejected = apply_track_first_persist_gate(rows)
        self.assertEqual(kept, [])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reject_reason_code"], "track_first_missing_bbox")

    def test_keeps_video_row_with_valid_bbox(self):
        rows = [
            {
                "source": "video",
                "detection_provider": "yolo",
                "species_name": "Great Tit",
                "frames": [{"t": 0.1, "bbox": [0.1, 0.2, 0.3, 0.4]}],
            }
        ]
        kept, rejected = apply_track_first_persist_gate(rows)
        self.assertEqual(len(rejected), 0)
        self.assertEqual(len(kept), 1)
        self.assertTrue(has_ingestible_track_rows(kept))
        self.assertEqual(count_ingestible_track_rows(kept), 1)

    def test_non_video_rows_pass_through(self):
        rows = [{"source": "mqtt", "detection_provider": "frigate", "frames": []}]
        kept, rejected = apply_track_first_persist_gate(rows)
        self.assertEqual(kept, rows)
        self.assertEqual(rejected, [])


if __name__ == "__main__":
    unittest.main()
