"""Save best_frame crops to data/dataset/train/<Species>/ for export and fine-tuning."""

import logging
import os
import re

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
) -> int:
    """
    Save best_frame from each detection to data/dataset/train/<Species>/.
    Returns count of saved images.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.warning("cv2 not available, skipping dataset save")
        return 0

    base = os.path.join(data_dir, "dataset", "train")
    saved = 0
    for i, d in enumerate(video_detections):
        bf = d.get("best_frame")
        if bf is None:
            continue
        conf = float(d.get("confidence", 0))
        if conf < min_confidence:
            continue
        species = d.get("species_name") or d.get("species") or d.get("name", "unknown")
        track_id = d.get("track_id", i)
        dirname = _sanitize_dirname(species)
        out_dir = os.path.join(base, dirname)
        os.makedirs(out_dir, exist_ok=True)
        filename = f"{video_id}_{track_id}_{i}.jpg"
        out_path = os.path.join(out_dir, filename)
        try:
            if isinstance(bf, np.ndarray):
                cv2.imwrite(out_path, bf)
            else:
                cv2.imwrite(out_path, bf)
            saved += 1
            logger.debug("Saved dataset crop: %s", out_path)
        except Exception as e:
            logger.warning("Failed to save dataset crop %s: %s", out_path, e)
    if saved > 0:
        logger.info("Saved %d dataset crops to %s", saved, base)
    return saved
