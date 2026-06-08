"""Tests for record_hires_crop helpers."""

from __future__ import annotations

import numpy as np

from record_hires_crop import (
    pick_bbox_and_timestamp,
    resolve_enrichment_crop,
    resolve_enrichment_crop_source,
    track_as_detection,
)


def test_resolve_enrichment_crop_source_defaults_auto():
    assert resolve_enrichment_crop_source({}, config_key="processor.classifier_crop_source") == "auto"
    assert (
        resolve_enrichment_crop_source(
            {"processor.classifier_crop_source": "record_hires"},
            config_key="processor.classifier_crop_source",
        )
        == "record_hires"
    )


def test_pick_bbox_and_timestamp_uses_key_frame_bbox():
    det = {
        "start_time": 1.0,
        "end_time": 3.0,
        "playback_timeline_synced": True,
        "frames": [{"t": 2.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        "key_frames": [{"t": 2.5, "score": 9.0, "bbox": [0.2, 0.3, 0.5, 0.6]}],
    }
    bbox, ts = pick_bbox_and_timestamp(det)
    assert bbox == [0.2, 0.3, 0.5, 0.6]
    assert ts == 2.5


def test_resolve_enrichment_crop_falls_back_to_lores():
    lores = np.zeros((32, 32, 3), dtype=np.uint8)
    det = track_as_detection(
        {
            "start_time": 0.0,
            "end_time": 1.0,
            "best_frame": lores,
            "frames": [],
        },
        camera_id="BirdBox",
    )
    crop, src = resolve_enrichment_crop(det, video_path=None, mode="best_frame_lores", lores_crop=lores)
    assert src == "best_frame_lores"
    assert crop is lores
