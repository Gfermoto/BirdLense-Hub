"""Dataset crop export helpers for finalized recordings."""

from __future__ import annotations

from typing import Any

from shared.detection_crop_contract import build_detection_crop_request


def _save_dataset_crops(*args: Any, **kwargs: Any) -> None:
    from dataset_saver import save_dataset_crops

    save_dataset_crops(*args, **kwargs)


def maybe_save_dataset_crops(
    config: Any,
    *,
    video_id: Any,
    video_detections: list[dict],
    data_dir: str,
    video_output: str,
) -> None:
    save_crops = config.get("processor.save_dataset_crops")
    if video_id is None or not save_crops or not video_detections:
        return
    raw_min_confidence = config.get("processor.dataset_min_confidence", 0.5)
    try:
        min_confidence = float(raw_min_confidence)
    except (TypeError, ValueError):
        min_confidence = 0.5
    candidates: list[dict] = []
    for detection in video_detections:
        try:
            confidence = float(detection.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < min_confidence:
            continue
        crop_request = build_detection_crop_request(
            best_frame=detection.get("best_frame"),
            frames=detection.get("frames"),
            start_time=detection.get("start_time", 0.0),
            end_time=detection.get("end_time", 0.0),
        )
        if crop_request.get("source_kind") == "none":
            continue
        candidates.append(detection)
    if not candidates:
        return
    _save_dataset_crops(
        candidates,
        video_id,
        data_dir,
        min_confidence=min_confidence,
        video_output_path=video_output,
    )
