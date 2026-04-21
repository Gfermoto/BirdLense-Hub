"""Save best_frame crops to data/dataset/train/<Species>/ for export and fine-tuning."""

import logging
import os
import re

from shared.detection_crop_contract import build_detection_crop_request

logger = logging.getLogger(__name__)


def _sanitize_dirname(name: str) -> str:
    """Sanitize species name for use as directory name. Format: Scientific (Common)."""
    # Replace problematic chars, collapse spaces
    s = re.sub(r'[<>:"/\\|?*]', "_", str(name).strip())
    s = re.sub(r"\s+", " ", s).strip()
    return s or "unknown"


def save_dataset_crops(
    video_detections: list,
    video_id: int,
    data_dir: str,
    min_confidence: float = 0.5,
    video_output_path: str | None = None,
) -> int:
    """
    Save best_frame from each detection to data/dataset/train/<Species>/.
    Returns count of saved images.
    """
    try:
        cv2_mod = globals().get("cv2")
        if cv2_mod is None:
            import cv2 as cv2_mod
    except ImportError:
        logger.warning("cv2 not available, skipping dataset save")
        return 0

    base = os.path.join(data_dir, "dataset", "train")
    saved = 0
    for i, d in enumerate(video_detections):
        conf = float(d.get("confidence", 0))
        if conf < min_confidence:
            continue
        crop_request = build_detection_crop_request(
            best_frame=d.get("best_frame"),
            frames=d.get("frames"),
            start_time=d.get("start_time", 0.0),
            end_time=d.get("end_time", 0.0),
        )
        crop_img = crop_request.get("best_frame")
        if crop_img is None and crop_request.get("source_kind") == "video_frames_bbox":
            crop_img = _extract_local_detection_crop(video_output_path, crop_request)
        if crop_img is None:
            continue
        species = d.get("species_name") or d.get("species") or d.get("name", "unknown")
        track_id = d.get("track_id", i)
        dirname = _sanitize_dirname(species)
        out_dir = os.path.join(base, dirname)
        os.makedirs(out_dir, exist_ok=True)
        filename = f"{video_id}_{track_id}_{i}.jpg"
        out_path = os.path.join(out_dir, filename)
        try:
            cv2_mod.imwrite(out_path, crop_img)
            saved += 1
            logger.debug("Saved dataset crop: %s", out_path)
        except Exception as e:
            logger.warning("Failed to save dataset crop %s: %s", out_path, e)
    if saved > 0:
        logger.info("Saved %d dataset crops to %s", saved, base)
    return saved


def _extract_local_detection_crop(video_output_path: str | None, crop_request: dict):
    if not video_output_path or not os.path.isfile(video_output_path):
        return None
    try:
        import cv2
    except ImportError:
        return None
    bbox = crop_request.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    cap = cv2.VideoCapture(video_output_path)
    try:
        offset_sec = max(0.0, float(crop_request.get("offset_sec") or 0.0))
        cap.set(cv2.CAP_PROP_POS_MSEC, offset_sec * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        h, w = frame.shape[:2]
        x1 = max(0, int(float(bbox[0]) * w))
        y1 = max(0, int(float(bbox[1]) * h))
        x2 = min(w, int(float(bbox[2]) * w))
        y2 = min(h, int(float(bbox[3]) * h))
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]
    finally:
        cap.release()
