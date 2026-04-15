import os
import sys
import unittest

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


if __name__ == '__main__':
    unittest.main()
