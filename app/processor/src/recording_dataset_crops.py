"""Dataset crop export helpers for finalized recordings."""

from __future__ import annotations

from typing import Any


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
    min_confidence = float(raw_min_confidence)
    _save_dataset_crops(
        video_detections,
        video_id,
        data_dir,
        min_confidence=min_confidence,
        video_output_path=video_output,
    )
