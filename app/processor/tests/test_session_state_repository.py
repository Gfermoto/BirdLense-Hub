import os
import sys
import tempfile

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from session_state_repository import SessionStateRepository


def _mk_repo():
    tmp = tempfile.TemporaryDirectory()
    db_path = os.path.join(tmp.name, 'state.db')
    repo = SessionStateRepository(db_path=db_path)
    return tmp, repo


def test_session_state_repository_persists_runtime_and_health_events():
    tmp, repo = _mk_repo()
    try:
        sid = repo.save_session_runtime(
            {
                'triggered_camera': 'BirdBox',
                'duration_s': 12.3,
                'frames_seen': 80,
                'yolo_frames_ran': 80,
                'yolo_raw_boxes_total': 0,
                'session_extended_by_frigate_only': 7,
                'yolo_blind_confirmed': True,
                'video_file_ok': True,
            }
        )
        assert sid > 0
        hid = repo.append_detector_health_event(
            event_type='yolo_blind_confirmed',
            severity='warning',
            camera_id='BirdBox',
            details={'reason': 'synthetic'},
        )
        assert hid > 0
        rows = repo.recent_blind_sessions(camera_id='BirdBox', limit=5)
        assert len(rows) == 1
        assert int(rows[0]['yolo_frames_ran']) == 80
        assert int(rows[0]['yolo_raw_boxes_total']) == 0
    finally:
        tmp.cleanup()


def test_blind_confirmed_requires_consecutive_blind_sessions():
    tmp, repo = _mk_repo()
    try:
        for _ in range(2):
            repo.save_session_runtime(
                {
                    'triggered_camera': 'BirdBox',
                    'yolo_frames_ran': 50,
                    'yolo_raw_boxes_total': 0,
                    'session_extended_by_frigate_only': 9,
                }
            )
        assert repo.is_blind_confirmed(camera_id='BirdBox', min_recent_sessions=2)

        repo.save_session_runtime(
            {
                'triggered_camera': 'BirdBox',
                'yolo_frames_ran': 50,
                'yolo_raw_boxes_total': 3,
                'session_extended_by_frigate_only': 1,
            }
        )
        assert not repo.is_blind_confirmed(camera_id='BirdBox', min_recent_sessions=2)
    finally:
        tmp.cleanup()


def test_blind_confirmed_respects_duration_and_frame_thresholds():
    tmp, repo = _mk_repo()
    try:
        repo.save_session_runtime(
            {
                'triggered_camera': 'BirdBox',
                'duration_s': 8.0,
                'yolo_frames_ran': 60,
                'yolo_raw_boxes_total': 0,
                'session_extended_by_frigate_only': 40,
            }
        )
        assert not repo.is_blind_confirmed(
            camera_id='BirdBox',
            min_recent_sessions=1,
            min_yolo_frames=180,
            min_frigate_only_frames=120,
            min_duration_seconds=30.0,
        )

        repo.save_session_runtime(
            {
                'triggered_camera': 'BirdBox',
                'duration_s': 35.0,
                'yolo_frames_ran': 245,
                'yolo_raw_boxes_total': 0,
                'session_extended_by_frigate_only': 180,
            }
        )
        assert repo.is_blind_confirmed(
            camera_id='BirdBox',
            min_recent_sessions=1,
            min_yolo_frames=180,
            min_frigate_only_frames=120,
            min_duration_seconds=30.0,
        )
    finally:
        tmp.cleanup()
