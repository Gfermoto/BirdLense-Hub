import os
import sys
import unittest
from argparse import Namespace

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

import recording_session as rs  # noqa: E402


class _MotionDetector:
    def __init__(self, active=False):
        self.active = active
        self.calls = []

    def has_recent_frigate_activity(self, camera=None, max_age_seconds=0):
        self.calls.append((camera, max_age_seconds))
        return self.active


class _Aggregator:
    def __init__(self, active=False):
        self.active = active
        self.calls = []

    def has_recent_frigate_activity(self, camera_ids=None, max_age_seconds=0, min_confidence=0.0):
        self.calls.append((tuple(sorted(camera_ids or [])), max_age_seconds, min_confidence))
        return self.active


class TestRecordingSessionActivity(unittest.TestCase):
    def test_session_activity_camera_ids_include_multi_camera_group(self):
        session = rs.MotionRecordingSession.__new__(rs.MotionRecordingSession)

        old_get = rs.app_config.get
        rs.app_config.get = lambda key, default=None: [['cam-a', 'cam-b']] if key == 'processor.multi_camera_groups' else default
        try:
            cameras = session._session_activity_camera_ids('cam-a')
        finally:
            rs.app_config.get = old_get

        self.assertEqual(cameras, ['cam-a', 'cam-b'])

    def test_session_activity_uses_grouped_camera_recent_frigate_event(self):
        session = rs.MotionRecordingSession.__new__(rs.MotionRecordingSession)
        session.motion_detector = _MotionDetector(active=False)
        session.mqtt_aggregator = _Aggregator(active=True)

        old_get = rs.app_config.get
        rs.app_config.get = lambda key, default=None: [['cam-a', 'cam-b']] if key == 'processor.multi_camera_groups' else default
        try:
            active = session._has_session_activity(
                has_detections=False,
                camera_id='cam-a',
                frigate_hold_seconds=6.0,
            )
        finally:
            rs.app_config.get = old_get

        self.assertTrue(active)
        self.assertEqual(session.motion_detector.calls, [('cam-a', 6.0)])
        self.assertEqual(session.mqtt_aggregator.calls, [(('cam-a', 'cam-b'), 6.0, 0.0)])

    def test_session_activity_falls_back_to_default_camera_when_trigger_camera_missing(self):
        session = rs.MotionRecordingSession.__new__(rs.MotionRecordingSession)
        session.motion_detector = _MotionDetector(active=False)
        session.mqtt_aggregator = _Aggregator(active=True)
        session.default_camera_id = 'cam-default'

        old_get = rs.app_config.get
        rs.app_config.get = lambda key, default=None: [] if key == 'processor.multi_camera_groups' else default
        try:
            active = session._has_session_activity(
                has_detections=False,
                camera_id=None,
                frigate_hold_seconds=6.0,
            )
        finally:
            rs.app_config.get = old_get

        self.assertTrue(active)
        self.assertEqual(session.mqtt_aggregator.calls, [(('cam-default',), 6.0, 0.0)])

    def test_session_activity_without_any_camera_scope_does_not_query_aggregator(self):
        session = rs.MotionRecordingSession.__new__(rs.MotionRecordingSession)
        session.motion_detector = _MotionDetector(active=False)
        session.mqtt_aggregator = _Aggregator(active=True)
        session.default_camera_id = None

        old_get = rs.app_config.get
        rs.app_config.get = lambda key, default=None: [] if key == 'processor.multi_camera_groups' else default
        try:
            active = session._has_session_activity(
                has_detections=False,
                camera_id=None,
                frigate_hold_seconds=6.0,
            )
        finally:
            rs.app_config.get = old_get

        self.assertFalse(active)
        self.assertEqual(session.mqtt_aggregator.calls, [])


class _NoopFpsTracker:
    def reset(self):
        return None

    def log_summary(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _MediaSource:
    def __init__(self, frames):
        self._frames = list(frames)
        self.record_path = None
        self.stopped = False
        self.video_path = "dummy.mp4"

    def start_recording(self, path):
        self.record_path = path

    def stop_recording(self):
        self.stopped = True

    def capture(self):
        if not self._frames:
            return None
        return self._frames.pop(0)

    def get_frame_time(self):
        return None


class _FrameProcessor:
    def __init__(self):
        self.tracks = {}
        self.last_run_stats = {}
        self.run_calls = 0
        self.pipeline_policy = {}

    def reset(self):
        self.tracks = {}
        self.last_run_stats = {}

    def set_session_context(self, _ctx):
        return None

    def run(self, frame, frame_time=None, camera_overrides=None, classification_frame=None):
        self.run_calls += 1
        self.last_run_stats = {}
        return False


class _DecisionMaker:
    def __init__(self):
        self.species_confidence_overrides = {}

    def reset(self):
        return None

    def apply_runtime_overrides(self, overrides):
        return None

    def update_has_detections(self, has_detections):
        return None

    def get_first_species_result(self, tracks):
        return None

    def decide_stop_recording(self):
        return False


class _MotionDetectorRunStub:
    def get_triggered_camera(self):
        return "cam-a"

    def get_triggered_by(self):
        return "opencv"

    def has_recent_frigate_activity(self, camera=None, max_age_seconds=0):
        return False


class _AggregatorRunStub:
    def has_recent_frigate_activity(self, camera_ids=None, max_age_seconds=0, min_confidence=0.0):
        return False


class TestRecordingSessionCaptureRetry(unittest.TestCase):
    def _build_session(self, media_source):
        return rs.MotionRecordingSession(
            args=Namespace(input=False),
            api=object(),
            motion_detector=_MotionDetectorRunStub(),
            mqtt_aggregator=_AggregatorRunStub(),
            frame_processor=_FrameProcessor(),
            decision_maker=_DecisionMaker(),
            merged_overrides={},
            media_source_ref=[media_source],
            get_media_source=lambda camera_id: media_source,
            default_camera_id="cam-a",
            scales_topic_arg=None,
            data_dir="data",
            fps_tracker=_NoopFpsTracker(),
            file_test_runtime=None,
        )

    def test_live_source_retries_empty_frame_before_abort(self):
        media_source = _MediaSource([None, object(), None, None])
        session = self._build_session(media_source)
        counters = []
        finalized = []
        old_get = rs.app_config.get
        old_inc = rs.inc_counter
        old_finalize = rs.finalize_motion_recording
        rs.app_config.get = lambda key, default=None: {
            "video.source": "go2rtc",
            "processor.capture_none_frame_retries": 1,
            "processor.capture_none_frame_retry_sleep_ms": 0,
            "processor.frigate_activity_hold_seconds": 0,
            "processor.multi_camera_groups": [],
        }.get(key, default)
        rs.inc_counter = lambda name, delta=1: counters.append((name, int(delta)))
        rs.finalize_motion_recording = lambda *args, **kwargs: finalized.append(kwargs)
        try:
            session.run()
        finally:
            rs.app_config.get = old_get
            rs.inc_counter = old_inc
            rs.finalize_motion_recording = old_finalize

        counter_names = [name for name, _ in counters]
        self.assertEqual(session.frame_processor.run_calls, 1)
        self.assertIn("recording_capture_none_frame_total", counter_names)
        self.assertIn("recording_capture_none_frame_recovered_total", counter_names)
        self.assertIn("recording_capture_none_frame_abort_total", counter_names)
        self.assertEqual(len(finalized), 1)

    def test_file_source_stops_on_first_empty_frame_without_retry(self):
        media_source = _MediaSource([None])
        session = self._build_session(media_source)
        counters = []
        old_get = rs.app_config.get
        old_inc = rs.inc_counter
        old_finalize = rs.finalize_motion_recording
        rs.app_config.get = lambda key, default=None: {
            "video.source": "file",
            "processor.capture_none_frame_retries": 5,
            "processor.capture_none_frame_retry_sleep_ms": 0,
            "processor.frigate_activity_hold_seconds": 0,
            "processor.multi_camera_groups": [],
        }.get(key, default)
        rs.inc_counter = lambda name, delta=1: counters.append((name, int(delta)))
        rs.finalize_motion_recording = lambda *args, **kwargs: None
        try:
            session.run()
        finally:
            rs.app_config.get = old_get
            rs.inc_counter = old_inc
            rs.finalize_motion_recording = old_finalize

        counter_names = [name for name, _ in counters]
        self.assertEqual(session.frame_processor.run_calls, 0)
        self.assertNotIn("recording_capture_none_frame_total", counter_names)
        self.assertNotIn("recording_capture_none_frame_abort_total", counter_names)


if __name__ == '__main__':
    unittest.main()
