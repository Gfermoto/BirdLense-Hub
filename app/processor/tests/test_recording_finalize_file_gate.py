import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)

import recording_finalize as recording_finalize_mod  # noqa: E402
from recording_finalize import finalize_motion_recording  # noqa: E402


class TestRecordingFinalizeFileGate(unittest.TestCase):
    def test_skips_api_when_output_video_missing(self):
        api = MagicMock()
        motion_detector = MagicMock()
        mqtt_aggregator = None
        frame_processor = MagicMock(tracks={})
        decision_maker = MagicMock()
        decision_maker.get_decisions.return_value = [{
            'accepted': True,
            'species_name': 'Bird',
            'start_time': 0.0,
            'end_time': 2.0,
            'confidence': 0.9,
            'frames': [],
            'decision_reason': 'accepted_species',
            'decision_kind': 'accepted_species',
            'visit_eligible': True,
            'notification_eligible': True,
        }]

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = os.path.join(tmp, 'session')
            os.makedirs(out_dir, exist_ok=True)
            missing_video = os.path.join(out_dir, 'missing.mp4')
            with patch('recording_finalize.generate_spectrogram', return_value=False):
                finalize_motion_recording(
                    api,
                    motion_detector,
                    mqtt_aggregator,
                    frame_processor,
                    decision_maker,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    output_path_physical=out_dir,
                    output_path_logical='data/recordings/2026/04/07/120000',
                    video_output=missing_video,
                    video_path_for_api='data/recordings/2026/04/07/120000/video.mp4',
                    scales_topic_arg=None,
                    data_dir=tmp,
                )

        api.create_video.assert_not_called()
        api.notify_species.assert_not_called()

    def test_skips_telegram_when_below_min_confidence_to_notify(self):
        api = MagicMock()
        api.create_video.return_value = {'video_id': 7}
        motion_detector = MagicMock()
        mqtt_aggregator = None
        frame_processor = MagicMock(tracks={})
        decision_maker = MagicMock()
        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        decision_maker.get_decisions.return_value = [{
            'accepted': True,
            'species_name': 'Great Tit',
            'start_time': 0.0,
            'end_time': 1.0,
            'confidence': 0.40,
            'frames': [{'t': 0.0, 'bbox': [0.0, 0.0, 1.0, 1.0]}],
            'key_frames': [],
            'best_frame': frame,
            'decision_reason': 'accepted_species',
            'decision_kind': 'accepted_species',
            'visit_eligible': True,
            'notification_eligible': True,
        }]

        def fake_cfg_get(key, default=None):
            mapping = {
                'detection.merge_window_seconds': 5,
                'processor.min_track_duration': 1,
                'processor.generate_spectrogram_always': False,
                'processor.save_dataset_crops': False,
                'integrations.scales.enabled': False,
                'processor.min_confidence_to_notify': 0.55,
                'processor.min_confidence_to_process': 0.30,
                'detection.min_confidence_to_store': 0.05,
                'processor.dataset_min_confidence': 0.5,
            }
            return mapping.get(key, default)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = os.path.join(tmp, 'session')
            os.makedirs(out_dir, exist_ok=True)
            video_path = os.path.join(out_dir, 'clip.mp4')
            vw = cv2.VideoWriter(
                video_path,
                cv2.VideoWriter_fourcc(*'mp4v'),
                2.0,
                (32, 32),
            )
            vw.write(frame)
            vw.release()
            with patch.object(
                recording_finalize_mod.app_config,
                'get',
                side_effect=fake_cfg_get,
            ), patch(
                'recording_finalize.build_fused_video_detections',
                side_effect=lambda det, *a, **k: det,
            ), patch('recording_finalize.generate_spectrogram', return_value=False):
                finalize_motion_recording(
                    api,
                    motion_detector,
                    mqtt_aggregator,
                    frame_processor,
                    decision_maker,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    output_path_physical=out_dir,
                    output_path_logical='data/recordings/2026/04/08/120000',
                    video_output=video_path,
                    video_path_for_api='data/recordings/2026/04/08/120000/video.mp4',
                    scales_topic_arg=None,
                    data_dir=tmp,
                )

        api.create_video.assert_called_once()
        api.notify_species.assert_not_called()


if __name__ == '__main__':
    unittest.main()
