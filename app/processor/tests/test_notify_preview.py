"""Regression tests for Telegram preview generation."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
app_path = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.append(src_path)
sys.path.append(app_path)

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


class TestEncodeNotifyPreview(unittest.TestCase):
    def test_notify_preview_retries_until_video_becomes_readable(self):
        frame = np.full((12, 12, 3), 255, dtype=np.uint8)
        captures = [
            _FakeCapture(False, None),
            _FakeCapture(True, frame),
        ]
        opened_attempts = []

        def fake_video_capture(_path):
            opened_attempts.append(True)
            return captures.pop(0)

        with patch.object(
            notify_preview_encode_mod.cv2,
            'VideoCapture',
            fake_video_capture,
        ), patch.object(
            notify_preview_encode_mod.cv2,
            'imencode',
            lambda *_a, **_k: (True, np.array([1, 2, 3], dtype=np.uint8)),
        ), patch.object(
            notify_preview_encode_mod.time,
            'sleep',
            lambda _d: None,
        ):
            image_b64, source = encode_notify_preview_base64(
                {
                    'start_time': 3.0,
                    'end_time': 5.0,
                    'frames': [],
                },
                '/tmp/fake-video.mp4',
            )

        self.assertIsNotNone(image_b64)
        self.assertEqual(source, 'full_frame')
        self.assertEqual(len(opened_attempts), 2)

    def test_prefers_best_frame_when_scored_over_video_bbox(self):
        """TG preview: crop at detection time, not lagging tracker bbox on file."""
        bf = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        frame = np.full((20, 20, 3), 255, dtype=np.uint8)

        def fake_video_capture(_path):
            return _FakeCapture(True, frame)

        with patch.object(
            notify_preview_encode_mod.cv2,
            'VideoCapture',
            fake_video_capture,
        ), patch.object(
            notify_preview_encode_mod.cv2,
            'imencode',
            lambda *_a, **_k: (True, np.array([1, 2, 3], dtype=np.uint8)),
        ), patch.object(
            notify_preview_encode_mod.time,
            'sleep',
            lambda _d: None,
        ):
            image_b64, source = encode_notify_preview_base64(
                {
                    'best_frame': bf,
                    'best_frame_score': 20.0,
                    'start_time': 0.0,
                    'end_time': 2.0,
                    'frames': [
                        {'bbox': [0.1, 0.1, 0.5, 0.5], 't': 1.0},
                    ],
                },
                '/tmp/fake-video.mp4',
            )

        self.assertIsNotNone(image_b64)
        self.assertEqual(source, 'best_frame')


class TestDetectionStackWeights(unittest.TestCase):
    def test_build_detection_stack_raises_when_binary_weights_missing(self):
        import detection_stack as detection_stack_mod  # noqa: E402

        class _Cfg:
            def get(self, key, default=None):
                mapping = {
                    'processor.inference_backend': 'torch',
                    'processor.classifier_inference_backend': 'torch',
                    'processor.models.binary': '/tmp/missing_binary.pt',
                    'processor.models.classifier': '/tmp/ok_classifier.pt',
                    'processor.detection_strategy': 'two_stage',
                    'processor.regional_species': [],
                    'processor.track_regen_ignore_regional_species': True,
                    'processor.tracker': 'bytetrack.yaml',
                    'processor.max_record_seconds': 60,
                    'processor.max_inactive_seconds': 10,
                    'processor.min_track_duration': 1,
                    'processor.min_confidence_to_process': 0.1,
                    'processor.post_record_seconds': 0,
                    'detection.min_confidence_to_store': 0.3,
                    'processor.classifier_fallback_bird': True,
                }
                return mapping.get(key, default)

        def _isfile(path):
            return str(path) == '/tmp/ok_classifier.pt'

        with patch.object(detection_stack_mod.os.path, 'isfile', _isfile):
            with self.assertRaises(FileNotFoundError) as ctx:
                detection_stack_mod.build_detection_stack(_Cfg())
        err = str(ctx.exception).lower()
        self.assertIn('binary', err)
        self.assertIn('missing_binary', err)

    def test_build_detection_stack_openvino_size_mismatch_raises_clear_error(self):
        import detection_stack as detection_stack_mod  # noqa: E402

        with tempfile.TemporaryDirectory() as d:
            ov_dir = os.path.join(d, 'ov')
            os.makedirs(ov_dir, exist_ok=True)
            with open(os.path.join(ov_dir, 'best.xml'), 'w', encoding='utf-8') as f:
                f.write('<net />')
            with open(os.path.join(ov_dir, 'best.bin'), 'wb') as f:
                f.write(b'\x00')
            with open(os.path.join(ov_dir, 'metadata.yaml'), 'w', encoding='utf-8') as f:
                f.write('imgsz:\n- 960\n- 960\n')
            cls_pt = os.path.join(d, 'classifier.pt')
            with open(cls_pt, 'wb') as f:
                f.write(b'pt')

            class _Cfg:
                def get(self, key, default=None):
                    mapping = {
                        'processor.inference_backend': 'openvino',
                        'processor.classifier_inference_backend': 'torch',
                        'processor.models.binary_openvino': ov_dir,
                        'processor.models.classifier': cls_pt,
                        'processor.binary_imgsz': 640,
                        'processor.detection_strategy': 'two_stage',
                        'processor.regional_species': [],
                        'processor.track_regen_ignore_regional_species': True,
                        'processor.tracker': 'bytetrack.yaml',
                        'processor.max_record_seconds': 60,
                        'processor.max_inactive_seconds': 10,
                        'processor.min_track_duration': 1,
                        'processor.min_confidence_to_process': 0.1,
                        'processor.post_record_seconds': 0,
                        'detection.min_confidence_to_store': 0.3,
                        'processor.classifier_fallback_bird': True,
                    }
                    return mapping.get(key, default)

            with self.assertRaises(RuntimeError) as ctx:
                detection_stack_mod.build_detection_stack(_Cfg())
            err = str(ctx.exception)
            self.assertIn('input-size mismatch', err)
            self.assertIn('model expects 960', err)


if __name__ == '__main__':
    unittest.main()
