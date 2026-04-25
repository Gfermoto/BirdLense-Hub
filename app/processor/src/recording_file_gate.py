"""Recording output file validation helpers."""

from __future__ import annotations

import os


def _is_playable_video_file(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        if os.path.getsize(path) <= 1024:
            return False
        import cv2

        cap = cv2.VideoCapture(path)
        try:
            if not cap.isOpened():
                return False
            ok, _frame = cap.read()
            return bool(ok)
        finally:
            cap.release()
    except Exception:
        return False
