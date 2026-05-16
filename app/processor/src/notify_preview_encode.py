"""Превью для Telegram/API: кадр из файла ролика или best_frame."""

import logging
import time

import cv2

logger = logging.getLogger(__name__)


def encode_notify_preview_base64(detection: dict, video_file_path: str) -> tuple[str | None, str]:
    """(image_base64, source): bbox_crop | full_frame | best_frame | none.

    Сначала кадр из сохранённого mp4 по bbox/времени трека — как в плеере.
    Иначе in-memory best_frame мог не совпасть с тем, что видно на видео.
    """
    try:
        import base64
        import numpy as np

        def _pick_timestamp() -> float:
            try:
                st = float(detection.get("start_time") or 0)
                et = float(detection.get("end_time") or st)
                if et > st:
                    return st + (et - st) * 0.5
                return st
            except Exception:
                logger.debug("_pick_timestamp fallback 0", exc_info=True)
                return 0.0

        key_frames = detection.get("key_frames") or []
        best_kf = None
        if isinstance(key_frames, list) and key_frames:
            dict_frames = [kf for kf in key_frames if isinstance(kf, dict)]
            if dict_frames:
                best_kf = max(
                    dict_frames,
                    key=lambda k: float(k.get("score") or 0.0),
                )

        frames = detection.get("frames") or []
        mid = frames[len(frames) // 2] if isinstance(frames, list) and frames else None
        bbox = mid.get("bbox") if isinstance(mid, dict) else None
        if isinstance(mid, dict):
            t = float(mid.get("t") or _pick_timestamp())
        else:
            t = _pick_timestamp()
        if best_kf is not None:
            bb = best_kf.get("bbox")
            if isinstance(bb, (list, tuple)) and len(bb) == 4:
                bbox = bb
            t = float(best_kf.get("t") or t)

        def _read_frame_with_retries(ts: float):
            retry_delays = (0.2, 0.5)
            max_attempts = 1 + len(retry_delays)
            for attempt in range(max_attempts):
                if attempt > 0:
                    time.sleep(retry_delays[attempt - 1])
                cap = cv2.VideoCapture(video_file_path)
                try:
                    if not cap.isOpened():
                        frame = None
                    else:
                        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                        if fps > 0.01:
                            n = max(0, int(ts * fps))
                            cap.set(cv2.CAP_PROP_POS_FRAMES, n)
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
            return None

        def _encode_from_video() -> tuple[str | None, str]:
            if not video_file_path:
                return None, "none"
            try:
                frame = _read_frame_with_retries(t)
                if frame is None:
                    return None, "none"
                h, w = frame.shape[:2]
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    x1 = max(0, min(w - 1, int(float(bbox[0]) * w)))
                    y1 = max(0, min(h - 1, int(float(bbox[1]) * h)))
                    x2 = max(x1 + 1, min(w, int(float(bbox[2]) * w)))
                    y2 = max(y1 + 1, min(h, int(float(bbox[3]) * h)))
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0:
                        params = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                        ok, buf = cv2.imencode(".jpg", crop, params)
                        if ok and buf is not None:
                            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                            return b64, "bbox_crop"

                params = [int(cv2.IMWRITE_JPEG_QUALITY), 88]
                ok, buf = cv2.imencode(".jpg", frame, params)
                if not ok or buf is None:
                    return None, "none"
                b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                return b64, "full_frame"
            except Exception as e:
                logging.warning("Encode video crop for notify failed: %s", e)
                return None, "none"

        if video_file_path:
            image_b64, src = _encode_from_video()
            if image_b64:
                return image_b64, src

        bf = detection.get("best_frame")
        if isinstance(bf, np.ndarray):
            try:
                ok, buf = cv2.imencode(".jpg", bf)
                if ok and buf is not None:
                    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                    return b64, "best_frame"
            except Exception as e:
                logging.warning("Encode best_frame for notify failed: %s", e)

        return None, "none"
    except Exception as e:
        logging.warning("Encode notify preview failed: %s", e)
        return None, "none"
