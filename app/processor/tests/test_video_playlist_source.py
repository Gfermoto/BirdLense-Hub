"""Tests for playlist file source mode."""

import os
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import numpy as np


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)

from sources.video_file_source import VideoPlaylistSource  # noqa: E402

_TEST_MAIN_SIZE = (640, 480)
_TEST_LORES_SIZE = (640, 480)


class _FakeCapture:
    def __init__(self, frames):
        self._frames = list(frames)
        self._opened = True

    def isOpened(self):
        return self._opened

    def get(self, _prop):
        return 25.0

    def set(self, _prop, _value):
        return True

    def read(self):
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self):
        self._opened = False


@contextmanager
def _patch_playlist_io(fake_video_capture):
    with patch("sources.video_file_source.cv2.VideoCapture", fake_video_capture), patch(
        "sources.video_file_source.cv2.resize",
        lambda frm, _size: frm,
    ), patch("stream_probe.probe_video_file", return_value=None), patch(
        "stream_probe.publish_probe_gauges",
    ):
        yield


class TestVideoPlaylistSource(unittest.TestCase):
    """Validate auto-switch to next file in playlist."""

    def test_playlist_switches_to_next_file(self):
        """Reads first file, then continues from second file."""
        frame = np.ones((4, 4, 3), dtype=np.uint8)
        captures = [_FakeCapture([frame]), _FakeCapture([frame])]
        opened = []

        def fake_video_capture(path, *args, **kwargs):
            opened.append(path)
            return captures.pop(0)

        with _patch_playlist_io(fake_video_capture):
            src = VideoPlaylistSource(
                ['/tmp/a.mp4', '/tmp/b.mp4'],
                main_size=_TEST_MAIN_SIZE,
                lores_size=_TEST_LORES_SIZE,
                loop=True,
            )
            self.assertIsNotNone(src.capture())
            self.assertIsNotNone(src.capture())
            self.assertEqual(opened[:2], ['/tmp/a.mp4', '/tmp/b.mp4'])

    def test_playlist_advances_on_each_start_recording(self):
        """Each new session moves to the next file in playlist."""
        frame = np.ones((4, 4, 3), dtype=np.uint8)
        captures = [
            _FakeCapture([frame]),
            _FakeCapture([frame]),
            _FakeCapture([frame]),
        ]
        opened = []

        def fake_video_capture(path, *args, **kwargs):
            opened.append(path)
            return captures.pop(0)

        with _patch_playlist_io(fake_video_capture):
            src = VideoPlaylistSource(
                ['/tmp/a.mp4', '/tmp/b.mp4'],
                main_size=_TEST_MAIN_SIZE,
                lores_size=_TEST_LORES_SIZE,
                loop=True,
                advance_on_start=True,
            )
            src.start_recording('/tmp/out1.mp4')
            src.start_recording('/tmp/out2.mp4')
            src.start_recording('/tmp/out3.mp4')
            self.assertEqual(opened[:3], ['/tmp/a.mp4', '/tmp/b.mp4', '/tmp/a.mp4'])

    def test_split_session_per_file_finalizes_between_clips(self):
        """After clip A ends, capture returns None once; next capture yields first frame of B."""
        frame_a = np.ones((3, 3, 3), dtype=np.uint8)
        frame_b = np.ones((3, 3, 3), dtype=np.uint8) * 2
        cap_a = _FakeCapture([frame_a])
        cap_b = _FakeCapture([frame_b])
        opened = []

        def fake_video_capture(path, *args, **kwargs):
            opened.append(path)
            if 'a.mp4' in path:
                return cap_a
            return cap_b

        with _patch_playlist_io(fake_video_capture):
            src = VideoPlaylistSource(
                ['/tmp/a.mp4', '/tmp/b.mp4'],
                main_size=_TEST_MAIN_SIZE,
                lores_size=_TEST_LORES_SIZE,
                loop=False,
                advance_on_start=False,
                split_session_per_file=True,
            )
            self.assertTrue(np.array_equal(src.capture(), frame_a))
            self.assertIsNone(src.capture())
            self.assertTrue(np.array_equal(src.capture(), frame_b))
            self.assertIsNone(src.capture())

    def test_playlist_segment_same_file_without_advance_on_start(self):
        frame = np.ones((4, 4, 3), dtype=np.uint8)
        cap_a = _FakeCapture([frame, frame])
        opened = []

        def fake_video_capture(path, *args, **kwargs):
            opened.append(path)
            return cap_a

        with _patch_playlist_io(fake_video_capture):
            src = VideoPlaylistSource(
                ['/tmp/a.mp4', '/tmp/b.mp4'],
                main_size=_TEST_MAIN_SIZE,
                lores_size=_TEST_LORES_SIZE,
                loop=True,
                advance_on_start=False,
            )
            src.start_recording('/tmp/out1.mp4')
            src.capture()
            src.start_recording('/tmp/out2.mp4')
            src.capture()
            self.assertEqual(opened, ['/tmp/a.mp4'])

    def test_playlist_no_loop_stops_after_last_file(self):
        """With loop=False, EOF on last clip yields None (folder run finishes)."""
        frame = np.ones((4, 4, 3), dtype=np.uint8)
        captures = [_FakeCapture([frame]), _FakeCapture([frame])]
        opened = []

        def fake_video_capture(path, *args, **kwargs):
            opened.append(path)
            return captures.pop(0)

        with _patch_playlist_io(fake_video_capture):
            src = VideoPlaylistSource(
                ['/tmp/a.mp4', '/tmp/b.mp4'],
                main_size=_TEST_MAIN_SIZE,
                lores_size=_TEST_LORES_SIZE,
                loop=False,
            )
            self.assertIsNotNone(src.capture())
            self.assertIsNotNone(src.capture())
            self.assertIsNone(src.capture())


if __name__ == '__main__':
    unittest.main()
