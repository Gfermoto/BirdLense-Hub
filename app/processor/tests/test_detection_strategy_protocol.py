"""[#295](https://github.com/Gfermoto/BirdLense-Hub/issues/295): FrameProcessor accepts a structural stub (Protocol), no YOLO."""

import os
import sys
import unittest
from unittest.mock import patch

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
sys.path.append(src_path)
sys.path.append(os.path.join(project_root, 'app'))

from frame_processor import FrameProcessor  # noqa: E402


class _StubStrategy:
    """Satisfies DetectionStrategyProtocol without inheriting from DetectionStrategy."""

    def __init__(self):
        self.detect_calls = []

    def detect(self, frame, tracker_config, *, min_confidence):
        self.detect_calls.append(
            {
                "tracker": tracker_config,
                "min_confidence": min_confidence,
                "shape": tuple(frame.shape),
            }
        )
        return []

    def reset(self):
        pass


class TestDetectionStrategyProtocol(unittest.TestCase):
    def test_frame_processor_invokes_stub_detect_with_min_confidence(self):
        rng = np.random.default_rng(42)
        # Bright, textured frame so LightLevelDetector passes (mean ≥25, std ≥20).
        img = rng.integers(50, 200, size=(240, 320, 3), dtype=np.uint8)

        stub = _StubStrategy()
        fp = FrameProcessor(stub, tracker="custom.yaml")

        import frame_processor as fp_mod

        def _cfg(key, default=None):
            if key == 'processor.min_confidence_binary':
                return 0.33
            return default

        with patch.object(fp_mod.app_config, 'get', side_effect=_cfg):
            ok = fp.run(img)

        self.assertFalse(ok)
        self.assertEqual(len(stub.detect_calls), 1)
        self.assertEqual(stub.detect_calls[0]['tracker'], 'custom.yaml')
        self.assertAlmostEqual(stub.detect_calls[0]['min_confidence'], 0.33)
        self.assertEqual(stub.detect_calls[0]['shape'], (240, 320, 3))

    def test_reset_delegates_to_strategy(self):
        stub = _StubStrategy()
        fp = FrameProcessor(stub)
        called = []

        def _reset():
            called.append(True)

        stub.reset = _reset
        fp.reset()
        self.assertEqual(called, [True])


if __name__ == '__main__':
    unittest.main()
