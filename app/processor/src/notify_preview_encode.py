"""Превью для Telegram/API: кадр из файла ролика или best_frame."""

import logging

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
                    t_mid = st + (et - st) * 0.5
                else:
                    t_mid = st
            except Exception:
                logger.debug("_pick_timestamp fallback 0", exc_info=True)
                t_mid = 0.0
            try:
                from dual_stream_timeline import (
                    apply_record_time_offset,
                    resolve_detect_record_time_offset_sec,
                )

                if detection.get("playback_timeline_synced"):
                    return max(0.0, float(t_mid))
                cam = str(detection.get("camera_id") or detection.get("triggered_camera") or "").strip()
                offset = resolve_detect_record_time_offset_sec(runtime_cfg, camera_id=cam or None)
                return apply_record_time_offset(t_mid, offset)
            except ImportError:
                return t_mid

        def _apply_offset_to_t(ts: float) -> float:
            if detection.get("playback_timeline_synced"):
                return max(0.0, float(ts))
            try:
                from dual_stream_timeline import (
                    apply_record_time_offset,
                    resolve_detect_record_time_offset_sec,
                )

                cam = str(detection.get("camera_id") or detection.get("triggered_camera") or "").strip()
                offset = resolve_detect_record_time_offset_sec(runtime_cfg, camera_id=cam or None)
                return apply_record_time_offset(float(ts), offset)
            except ImportError:
                return float(ts)

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
            t = _apply_offset_to_t(float(mid.get("t") or _pick_timestamp()))
        else:
            t = _pick_timestamp()
        if best_kf is not None:
            bb = best_kf.get("bbox")
            if isinstance(bb, (list, tuple)) and len(bb) == 4:
                bbox = bb
            t = _apply_offset_to_t(float(best_kf.get("t") or t))

        def _encode_from_video() -> tuple[str | None, str]:
            if not video_file_path:
                return None, "none"
            try:
                from record_hires_crop import read_record_hires_crop

                det_row = dict(detection)
                if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    det_row.setdefault("frames", [{"t": t, "bbox": list(bbox)}])
                crop = read_record_hires_crop(
                    video_file_path,
                    det_row,
                    pad_frac=_crop_pad_frac(),
                    runtime_cfg=runtime_cfg,
                )
                if crop is not None and crop.size > 0:
                    params = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                    ok, buf = cv2.imencode(".jpg", crop, params)
                    if ok and buf is not None:
                        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                            return b64, "record_hires" if _crop_pad_frac() > 0 else "bbox_crop"
                        return b64, "full_frame"
                cam = str(detection.get("camera_id") or detection.get("triggered_camera") or "").strip()
                logger.warning(
                    "notify_preview: record_hires empty path=%s t=%.3f camera=%s mode=%s synced=%s",
                    video_file_path,
                    t,
                    cam or "?",
                    _preview_mode(),
                    bool(detection.get("playback_timeline_synced")),
                )
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
