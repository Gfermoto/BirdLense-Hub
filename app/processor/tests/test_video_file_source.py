"""Unit tests for `VideoFileSource` test/loop behavior."""

import os
import sys
import unittest
from unittest.mock import patch

import numpy as np


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)

from sources.video_file_source import VideoFileSource  # noqa: E402


class _FakeCapture:
    def __init__(self, frames):
        self._frames = list(frames)
        self._opened = True

    def isOpened(self):
        return self._opened

    def get(self, _prop):
        return 25.0

    def read(self):
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self):
        self._opened = False


class TestVideoFileSource(unittest.TestCase):
    """Validate end-of-file and loop scenarios."""

    def test_capture_stops_at_end_without_loop(self):
        """Non-loop mode returns None at EOF."""
        frame = np.ones((4, 4, 3), dtype=np.uint8)
        captures = [_FakeCapture([frame])]

        def fake_video_capture(_path):
            return captures.pop(0)

        with patch(
            'sources.video_file_source.cv2.VideoCapture',
            fake_video_capture,
        ), patch(
            'sources.video_file_source.VideoFileSource._init_fps_from_probe',
            lambda self: setattr(self, 'source_fps', 25.0),
        ), patch('sources.video_file_source.cv2.resize', lambda frm, _size: frm):
            src = VideoFileSource(
                '/tmp/test.mp4',
                main_size=(640, 480),
                lores_size=(640, 480),
                loop=False,
            )
            self.assertIsNotNone(src.capture())
            self.assertIsNone(src.capture())

    def test_capture_restarts_from_beginning_with_loop(self):
        """Loop mode reopens source and continues frames."""
        frame = np.ones((4, 4, 3), dtype=np.uint8)
        captures = [_FakeCapture([frame]), _FakeCapture([frame])]
        open_calls = []

        def fake_video_capture(_path):
            open_calls.append(1)
            return captures.pop(0)

        with patch(
            'sources.video_file_source.cv2.VideoCapture',
            fake_video_capture,
        ), patch(
            'sources.video_file_source.VideoFileSource._init_fps_from_probe',
            lambda self: setattr(self, 'source_fps', 25.0),
        ), patch('sources.video_file_source.cv2.resize', lambda frm, _size: frm):
            src = VideoFileSource(
                '/tmp/test.mp4',
                main_size=(640, 480),
                lores_size=(640, 480),
                loop=True,
            )
            self.assertIsNotNone(src.capture())
            self.assertIsNotNone(src.capture())
            self.assertGreaterEqual(len(open_calls), 2)


if __name__ == '__main__':
    unittest.main()
