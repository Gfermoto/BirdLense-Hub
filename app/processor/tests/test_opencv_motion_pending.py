"""OpenCV motion: mark_pending after deferred recording."""

from __future__ import annotations

import numpy as np

from motion_detectors.opencv_motion import OpenCVMotionDetector


def test_requeue_last_trigger_delegates_to_mark_pending():
    det = OpenCVMotionDetector.__new__(OpenCVMotionDetector)
    det._pending_trigger = False
    assert det.requeue_last_trigger() is True
    assert det._pending_trigger is True


def test_mark_pending_rearms_check():
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    det = OpenCVMotionDetector(
        capture_fn=lambda: frame,
        threshold=25,
        min_contour_area=500,
        check_interval=0.05,
        check_every_n_frames=1,
        smart_trigger_enabled=True,
        min_consecutive_motion_frames=2,
    )
    det._prev_gray = det._gray_from_frame(frame, analyze=True)
    assert det.check() is False
    det.mark_pending()
    assert det.check() is True
