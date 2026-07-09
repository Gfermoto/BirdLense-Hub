import numpy as np

from yolo_geometry import frame_matches_target_wh, prepare_detector_frame


def test_skip_letterbox_when_native_detect_size():
    frame = np.zeros((576, 704, 3), dtype=np.uint8)
    assert frame_matches_target_wh(frame, (704, 576))
    out = prepare_detector_frame(frame, (704, 576))
    assert out.shape[:2] == (576, 704)
