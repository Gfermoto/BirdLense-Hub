"""Regression tests for Telegram preview generation."""

import os
import sys

import numpy as np


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
app_path = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.append(src_path)
sys.path.append(app_path)

import detection_stack as detection_stack_mod  # noqa: E402
import notify_preview_encode as notify_preview_encode_mod  # noqa: E402
from notify_preview_encode import encode_notify_preview_base64  # noqa: E402


class _FakeCapture:
    def __init__(self, opened, frame):
        self._opened = opened
        self._frame = frame

    def isOpened(self):
        return self._opened

    def get(self, _prop):
        return 25.0

    def set(self, _prop, _value):  # noqa: A003
        return True

    def read(self):
        return (self._frame is not None, self._frame)

    def release(self):
        return None


def test_notify_preview_retries_until_video_becomes_readable(monkeypatch):
    """Preview generation should retry if the clip is not readable immediately."""
    frame = np.full((12, 12, 3), 255, dtype=np.uint8)
    captures = [
        _FakeCapture(False, None),
        _FakeCapture(True, frame),
    ]
    opened_attempts = []

    def fake_video_capture(_path):
        opened_attempts.append(True)
        return captures.pop(0)

    monkeypatch.setattr(notify_preview_encode_mod.cv2, 'VideoCapture', fake_video_capture)
    monkeypatch.setattr(
        notify_preview_encode_mod.cv2,
        'imencode',
        lambda *_args, **_kwargs: (True, np.array([1, 2, 3], dtype=np.uint8)),
    )
    monkeypatch.setattr(notify_preview_encode_mod.time, 'sleep', lambda _delay: None)

    image_b64, source = encode_notify_preview_base64(
        {
            'start_time': 3.0,
            'end_time': 5.0,
            'frames': [],
        },
        '/tmp/fake-video.mp4',
    )

    assert image_b64 is not None
    assert source == 'full_frame'
    assert len(opened_attempts) == 2


def test_single_stage_model_path_accepts_ncnn_directory(monkeypatch):
    """NCNN directory paths must not fall back to yolov8n.pt."""
    ncnn_dir = '/tmp/nabirds_yolov8n_ncnn_model'

    monkeypatch.setattr(detection_stack_mod.os.path, 'isabs', lambda _path: True)
    monkeypatch.setattr(detection_stack_mod.os.path, 'isfile', lambda _path: False)
    monkeypatch.setattr(
        detection_stack_mod.os.path,
        'isdir',
        lambda path: path == ncnn_dir,
    )

    resolved = detection_stack_mod.resolve_single_stage_model_path(
        {'processor.models.single_stage': ncnn_dir},
        processor_root='/ignored',
    )

    assert resolved == ncnn_dir
