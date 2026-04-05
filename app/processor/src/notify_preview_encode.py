"""Кодирование превью для Telegram/API из best_frame или кадра видео."""

import logging
import time

import cv2


def encode_notify_preview_base64(detection: dict, video_file_path: str) -> tuple[str | None, str]:
    """Вернуть (image_base64, source): best_frame | bbox_crop | full_frame | none."""
    try:
        import base64
        import numpy as np

        bf = detection.get('best_frame')
        if isinstance(bf, np.ndarray):
            ok, buf = cv2.imencode('.jpg', bf)
            if ok and buf is not None:
                return base64.b64encode(buf.tobytes()).decode('ascii'), 'best_frame'
    except Exception as e:
        logging.warning("Encode best_frame for notify failed: %s", e)

    frames = detection.get('frames') or []
    if not video_file_path:
        return None, 'none'

    def _pick_timestamp() -> float:
        try:
            st = float(detection.get('start_time') or 0)
            et = float(detection.get('end_time') or st)
            if et > st:
                return st + (et - st) * 0.5
            return st
        except Exception:
            return 0.0

    mid = frames[len(frames) // 2] if isinstance(frames, list) and frames else None
    bbox = mid.get('bbox') if isinstance(mid, dict) else None
    t = float(mid.get('t') or _pick_timestamp()) if isinstance(mid, dict) else _pick_timestamp()

    def _read_frame_with_retries(ts: float):
        retry_delays = (0.0, 0.2, 0.5)
        for idx, delay in enumerate(retry_delays):
            cap = cv2.VideoCapture(video_file_path)
            try:
                if not cap.isOpened():
                    frame = None
                else:
                    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                    if fps > 0.01:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(ts * fps)))
                    else:
                        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, ts * 1000.0))
                    ok_local, frame = cap.read()
                    if not ok_local:
                        frame = None
                    if frame is None and ts > 0:
                        cap.set(cv2.CAP_PROP_POS_MSEC, 0.0)
                        ok_local, frame = cap.read()
                        if not ok_local:
                            frame = None
                if frame is not None:
                    return frame
            finally:
                cap.release()
            if idx + 1 < len(retry_delays):
                time.sleep(delay)
        return None

    try:
        import base64

        frame = _read_frame_with_retries(t)
        if frame is None:
            return None, 'none'
        h, w = frame.shape[:2]
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x1 = max(0, min(w - 1, int(float(bbox[0]) * w)))
            y1 = max(0, min(h - 1, int(float(bbox[1]) * h)))
            x2 = max(x1 + 1, min(w, int(float(bbox[2]) * w)))
            y2 = max(y1 + 1, min(h, int(float(bbox[3]) * h)))
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                ok, buf = cv2.imencode('.jpg', crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if ok and buf is not None:
                    return base64.b64encode(buf.tobytes()).decode('ascii'), 'bbox_crop'

        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok or buf is None:
            return None, 'none'
        return base64.b64encode(buf.tobytes()).decode('ascii'), 'full_frame'
    except Exception as e:
        logging.warning("Encode video crop for notify failed: %s", e)
        return None, 'none'
