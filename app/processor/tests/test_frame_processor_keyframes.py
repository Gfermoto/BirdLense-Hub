import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
sys.path.append(src_path)
sys.path.append(os.path.join(project_root, 'app'))

from frame_processor import FrameProcessor


class _DummyStrategy:
    def detect(self, frame, tracker_config, *, min_confidence, profile_overrides=None):
        return []

    def reset(self):
        return None


class TestFrameProcessorKeyFrames(unittest.TestCase):
    def test_update_track_keeps_best_scored_key_frames(self):
        fp = FrameProcessor(_DummyStrategy())
        fp.key_frame_limit = 2

        crop_low = np.zeros((10, 10, 3), dtype=np.uint8)
        crop_mid = np.zeros((20, 20, 3), dtype=np.uint8)
        crop_high = np.zeros((30, 30, 3), dtype=np.uint8)

        fp.update_track(1, 'Bird', None, 0.8, None, [0.1, 0.1, 0.2, 0.2], 0.0, crop_low, 10.0)
        fp.update_track(1, 'Bird', None, 0.8, None, [0.1, 0.1, 0.3, 0.3], 1.0, crop_high, 100.0)
        fp.update_track(1, 'Bird', None, 0.8, None, [0.1, 0.1, 0.25, 0.25], 2.0, crop_mid, 50.0)

        track = fp.tracks[1]
        self.assertEqual(len(track['key_frames']), 2)
        self.assertGreaterEqual(
            track['key_frames'][0]['score'],
            track['key_frames'][1]['score'],
        )
        self.assertIs(track['best_frame'], crop_high)


if __name__ == '__main__':
    unittest.main()
