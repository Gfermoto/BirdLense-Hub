"""Превью для Telegram/API: кадр из файла ролика или best_frame."""

import logging
import time

import cv2

logger = logging.getLogger(__name__)


def encode_notify_preview_base64(
    detection: dict,
    video_file_path: str,
    *,
    runtime_cfg: dict | None = None,
) -> tuple[str | None, str]:
    """(image_base64, source): best_frame | record_hires | bbox_crop | full_frame | none.

    ``processor.notify_preview_source``:
      - best_frame_lores — detect-stream crop (default, TG-quality on lores)
      - record_hires — main MP4 crop by remapped bbox + pad
      - auto — record_hires when video+bbox exist, else best_frame_lores
    """
    try:
        import base64
        import numpy as np

        def _preview_mode() -> str:
            raw = "best_frame_lores"
            if runtime_cfg is not None:
                raw = str(runtime_cfg.get("processor.notify_preview_source") or raw).strip().lower()
            else:
                try:
                    from app_config.app_config import app_config

                    raw = str(app_config.get("processor.notify_preview_source") or raw).strip().lower()
                except ImportError:
                    pass
            if raw in {"best_frame_lores", "record_hires", "auto"}:
                return raw
            return "best_frame_lores"

        def _crop_pad_frac() -> float:
            raw = 0.06
            if runtime_cfg is not None:
                try:
                    raw = float(runtime_cfg.get("processor.notify_preview_crop_pad_frac") or raw)
                except (TypeError, ValueError):
                    pass
            else:
                try:
                    from app_config.app_config import app_config

                    raw = float(app_config.get("processor.notify_preview_crop_pad_frac") or raw)
                except (TypeError, ValueError):
                    pass
            return max(0.0, min(0.25, raw))

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

        def _crop_has_signal(crop: np.ndarray) -> bool:
            if crop is None or crop.size == 0:
                return False
            try:
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
                return float(gray.std()) >= 8.0
            except Exception:
                return True

        def _encode_from_video() -> tuple[str | None, str]:
            if not video_file_path:
                return None, "none"
            try:
                frame = _read_frame_with_retries(t)
                if frame is None:
                    return None, "none"
                h, w = frame.shape[:2]
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    pad = _crop_pad_frac()
                    bw = float(bbox[2]) - float(bbox[0])
                    bh = float(bbox[3]) - float(bbox[1])
                    x1n = max(0.0, float(bbox[0]) - bw * pad)
                    y1n = max(0.0, float(bbox[1]) - bh * pad)
                    x2n = min(1.0, float(bbox[2]) + bw * pad)
                    y2n = min(1.0, float(bbox[3]) + bh * pad)
                    x1 = max(0, min(w - 1, int(x1n * w)))
                    y1 = max(0, min(h - 1, int(y1n * h)))
                    x2 = max(x1 + 1, min(w, int(x2n * w)))
                    y2 = max(y1 + 1, min(h, int(y2n * h)))
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0 and _crop_has_signal(crop):
                        params = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                        ok, buf = cv2.imencode(".jpg", crop, params)
                        if ok and buf is not None:
                            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                            return b64, "record_hires" if pad > 0 else "bbox_crop"

                params = [int(cv2.IMWRITE_JPEG_QUALITY), 88]
                ok, buf = cv2.imencode(".jpg", frame, params)
                if ok and buf is not None:
                    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                    return b64, "full_frame"
                return None, "none"
            except Exception as e:
                logging.warning("Encode video crop for notify failed: %s", e)
                return None, "none"

        def _encode_best_frame() -> tuple[str | None, str]:
            bf = detection.get("best_frame")
            if not isinstance(bf, np.ndarray) or bf.size <= 0:
                return None, "none"
            try:
                ok, buf = cv2.imencode(".jpg", bf, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if ok and buf is not None:
                    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                    return b64, "best_frame"
            except Exception as e:
                logging.warning("Encode best_frame for notify failed: %s", e)
            return None, "none"

        mode = _preview_mode()
        best_frame_score = float(detection.get("best_frame_score") or 0.0)

        if mode in {"record_hires", "auto"} and video_file_path:
            image_b64, src = _encode_from_video()
            if image_b64:
                return image_b64, src

        if mode == "record_hires":
            image_b64, src = _encode_best_frame()
            if image_b64:
                return image_b64, src
            return None, "none"

        if best_frame_score > 0.0:
            image_b64, src = _encode_best_frame()
            if image_b64:
                return image_b64, src

        if video_file_path:
            image_b64, src = _encode_from_video()
            if image_b64:
                return image_b64, src

        return _encode_best_frame()
    except Exception as e:
        logging.warning("Encode notify preview failed: %s", e)
        return None, "none"
