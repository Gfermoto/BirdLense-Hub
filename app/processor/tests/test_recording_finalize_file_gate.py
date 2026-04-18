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
            ), patch('recording_finalize.generate_spectrogram', return_value=False), patch(
                'recording_finalize._is_playable_video_file',
                return_value=True,
            ):
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
                    recording_context={
                        'triggered_camera': 'feeder-cam',
                        'frigate_activity_hold_seconds': 6.0,
                    },
                )

        api.create_video.assert_called_once()
        api.notify_species.assert_not_called()
        api.activity_log.assert_any_call(
            'decision_trace',
            unittest.mock.ANY,
        )
        trace_payload = api.activity_log.call_args_list[-1].args[1]
        self.assertEqual(trace_payload['decision_contract_version'], '2026-04-yolo-first-v1')
        self.assertEqual(trace_payload['outcome_summary']['persisted_track_count'], 1)
        self.assertEqual(trace_payload['outcome_summary']['review_only_count'], 0)
        self.assertEqual(trace_payload['recording_context']['triggered_camera'], 'feeder-cam')
        self.assertEqual(trace_payload['recording_context']['frigate_activity_hold_seconds'], 6.0)
        self.assertEqual(trace_payload['recording_context']['runtime_signals'], {})

    def test_keeps_session_when_no_detections_file_source_flag(self):
        api = MagicMock()
        motion_detector = MagicMock()
        mqtt_aggregator = None
        frame_processor = MagicMock(tracks={})
        decision_maker = MagicMock()
        decision_maker.get_decisions.return_value = []

        def fake_cfg_get(key, default=None):
            mapping = {
                'detection.merge_window_seconds': 5,
                'processor.min_track_duration': 1,
                'processor.generate_spectrogram_always': False,
                'processor.save_dataset_crops': False,
                'integrations.scales.enabled': False,
                'detection.min_confidence_to_store': 0.36,
                'processor.keep_recording_when_no_detections': True,
                'video.source': 'file',
            }
            return mapping.get(key, default)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = os.path.join(tmp, 'session')
            os.makedirs(out_dir, exist_ok=True)
            video_path = os.path.join(out_dir, 'clip.mp4')
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
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
            ), patch('recording_finalize.generate_spectrogram', return_value=False), patch(
                'recording_finalize._is_playable_video_file',
                return_value=True,
            ):
                finalize_motion_recording(
                    api,
                    motion_detector,
                    mqtt_aggregator,
                    frame_processor,
                    decision_maker,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    output_path_physical=out_dir,
                    output_path_logical='data/recordings/2026/04/08/130000',
                    video_output=video_path,
                    video_path_for_api='data/recordings/2026/04/08/130000/video.mp4',
                    scales_topic_arg=None,
                    data_dir=tmp,
                )
            api.create_video.assert_not_called()
            self.assertTrue(os.path.isdir(out_dir))
            self.assertTrue(os.path.isfile(video_path))

    def test_decision_trace_keeps_frigate_generic_absorb_reason(self):
        api = MagicMock()
        api.create_video.return_value = {'video_id': 11}
        motion_detector = MagicMock()
        mqtt_aggregator = None
        frame_processor = MagicMock(tracks={})
        decision_maker = MagicMock()
        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        decision_maker.get_decisions.return_value = []

        fused = [{
            'accepted': True,
            'species_name': 'Eurasian Jay',
            'species': 'Eurasian Jay',
            'start_time': 0.0,
            'end_time': 4.0,
            'confidence': 0.79,
            'frames': [{'t': 0.0, 'bbox': [0.0, 0.0, 1.0, 1.0]}],
            'best_frame': frame,
            'decision_reason': 'absorbed_generic_into_frigate_species',
            'decision_reason_before_arbitration': 'frigate_standalone',
            'arbitration_reason': 'absorbed_generic_into_frigate_species',
            'decision_kind': 'frigate_standalone',
            'visit_eligible': True,
            'notification_eligible': True,
            'detection_provider': 'frigate',
            '_fusion_used': 'absorbed_generic_into_frigate_species',
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
                return_value=fused,
            ), patch('recording_finalize.generate_spectrogram', return_value=False), patch(
                'recording_finalize._is_playable_video_file',
                return_value=True,
            ):
                finalize_motion_recording(
                    api,
                    motion_detector,
                    mqtt_aggregator,
                    frame_processor,
                    decision_maker,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    output_path_physical=out_dir,
                    output_path_logical='data/recordings/2026/04/08/140000',
                    video_output=video_path,
                    video_path_for_api='data/recordings/2026/04/08/140000/video.mp4',
                    scales_topic_arg=None,
                    data_dir=tmp,
                )

        trace_payload = api.activity_log.call_args_list[-1].args[1]
        persisted = trace_payload['persisted_tracks']
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0]['decision_reason'], 'absorbed_generic_into_frigate_species')
        self.assertEqual(persisted[0]['decision_reason_before_arbitration'], 'frigate_standalone')
        self.assertEqual(persisted[0]['arbitration_reason'], 'absorbed_generic_into_frigate_species')
        self.assertEqual(persisted[0]['_fusion_used'], 'absorbed_generic_into_frigate_species')
        self.assertEqual(persisted[0]['primary_provider'], 'frigate')
        self.assertEqual(persisted[0]['threshold_path'], 'frigate_standalone_min_score+arbitration')
        self.assertTrue(persisted[0]['fallback_used'])
        self.assertEqual(persisted[0]['fallback_reason'], 'frigate_standalone')

    def test_decision_trace_includes_pipeline_fingerprint_and_scales_evidence(self):
        api = MagicMock()
        api.create_video.return_value = {'video_id': 11}
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
            'confidence': 0.84,
            'frames': [{'t': 0.0, 'bbox': [0.0, 0.0, 1.0, 1.0]}],
            'best_frame': frame,
            'decision_reason': 'accepted_species',
            'decision_kind': 'accepted_species',
            'visit_eligible': True,
            'notification_eligible': True,
        }]

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = os.path.join(tmp, 'session')
            binary_path = os.path.join(tmp, 'models/detection/weights/test-binary.pt')
            classifier_path = os.path.join(tmp, 'models/classification/weights/test-classifier.pt')
            fusion_path = os.path.join(tmp, 'models/fusion/test-fusion.onnx')
            os.makedirs(os.path.dirname(binary_path), exist_ok=True)
            os.makedirs(os.path.dirname(classifier_path), exist_ok=True)
            os.makedirs(os.path.dirname(fusion_path), exist_ok=True)
            for path in (binary_path, classifier_path, fusion_path):
                with open(path, 'wb') as fh:
                    fh.write(b'test-model')

            def fake_cfg_get(key, default=None):
                mapping = {
                    'detection.merge_window_seconds': 5,
                    'processor.min_track_duration': 1,
                    'processor.generate_spectrogram_always': False,
                    'processor.save_dataset_crops': False,
                    'processor.min_confidence_to_notify': 0.30,
                    'processor.min_confidence_to_process': 0.30,
                    'processor.min_seconds_between_recordings': 8,
                    'integrations.scales.enabled': True,
                    'integrations.scales.weight_estimate_enabled': True,
                    'integrations.scales.min_delta_kg_for_estimate': 0.012,
                    'integrations.scales.estimate_require_consecutive_spike': True,
                    'motion.source': 'frigate',
                    'video.source': 'go2rtc',
                    'processor.models.binary': binary_path,
                    'processor.models.classifier': classifier_path,
                    'detection.use_learned_fusion': True,
                    'detection.fusion_alpha': 0.6,
                    'detection.fusion_model_path': fusion_path,
                    'detection.min_confidence_to_store': 0.05,
                    'processor.dataset_min_confidence': 0.5,
                }
                return mapping.get(key, default)

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
            ), patch(
                'recording_finalize.generate_spectrogram',
                return_value=False,
            ), patch(
                'recording_finalize._is_playable_video_file',
                return_value=True,
            ), patch(
                'scale_sample_log.estimate_weight_delta_kg',
                return_value=(0.023, 4),
            ):
                finalize_motion_recording(
                    api,
                    motion_detector,
                    mqtt_aggregator,
                    frame_processor,
                    decision_maker,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    output_path_physical=out_dir,
                    output_path_logical='data/recordings/2026/04/15/120000',
                    video_output=video_path,
                    video_path_for_api='data/recordings/2026/04/15/120000/video.mp4',
                    scales_topic_arg='birdlense/scales',
                    data_dir=tmp,
                    recording_context={
                        'triggered_camera': 'feeder-cam',
                        'frigate_activity_hold_seconds': 6.0,
                        'pipeline_policy': {
                            'mode': 'live',
                            'regional_scope_mode': 'global_classifier_scope',
                        },
                        'runtime_signals': {
                            'yolo_ran': True,
                            'yolo_track_found': True,
                        },
                    },
                )
        trace_payload = api.activity_log.call_args_list[-1].args[1]
        self.assertIn('pipeline_fingerprint', trace_payload)
        self.assertEqual(trace_payload['pipeline_fingerprint']['fusion']['enabled'], True)
        self.assertIn('binary_model', trace_payload['pipeline_fingerprint'])
        self.assertIn('classifier_model', trace_payload['pipeline_fingerprint'])
        self.assertEqual(
            trace_payload['recording_context']['pipeline_policy']['regional_scope_mode'],
            'global_classifier_scope',
        )
        self.assertEqual(
            trace_payload['recording_context']['runtime_signals']['yolo_ran'],
            True,
        )
        self.assertEqual(
            trace_payload['runtime_contract_summary']['persisted_primary_provider_counts'],
            {'yolo': 1},
        )
        self.assertEqual(
            trace_payload['scales_evidence']['estimated_delta_kg'],
            0.023,
        )
        self.assertEqual(trace_payload['scales_evidence']['sample_count'], 4)


if __name__ == '__main__':
    unittest.main()
