"""Tests for record_hires_crop helpers."""

from __future__ import annotations

import numpy as np

from record_hires_crop import (
    enrichment_crop_require_best_keyframe,
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


def test_enrichment_crop_require_keyframe_default_linear():
    assert enrichment_crop_require_best_keyframe({"processor.pipeline_mode": "linear"}) is True
    assert enrichment_crop_require_best_keyframe({"processor.pipeline_mode": "legacy"}) is True
    assert enrichment_crop_require_best_keyframe({"processor.pipeline_mode": "dual"}) is False
    assert (
        enrichment_crop_require_best_keyframe(
            {"processor.pipeline_mode": "dual", "processor.enrichment_crop_require_keyframe": True}
        )
        is True
    )


def test_pick_bbox_uses_frames_when_keyframes_stripped_from_notify_payload():
    """Notify payload keeps frames + key_frame_count but not key_frames array."""
    det = {
        "start_time": 1.0,
        "end_time": 3.0,
        "frames": [{"t": 2.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        "key_frames": [],
    }
    bbox, ts = pick_bbox_and_timestamp(det, require_best_keyframe=True)
    assert bbox == [0.1, 0.2, 0.3, 0.4]
    assert ts == 2.0


def test_pick_bbox_rejects_blind_mid_frame_when_keyframes_present_but_invalid():
    det = {
        "start_time": 1.0,
        "end_time": 3.0,
        "frames": [{"t": 2.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        "key_frames": [{"t": 2.5, "score": 9.0}],
    }
    bbox, ts = pick_bbox_and_timestamp(det, require_best_keyframe=True)
    assert bbox is None
    assert ts == 2.5


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


def test_pick_bbox_prefers_key_frame_over_mid_frame():
    det = {
        "start_time": 0.0,
        "end_time": 10.0,
        "playback_timeline_synced": True,
        "frames": [
            {"t": 1.0, "bbox": [0.0, 0.0, 0.1, 0.1]},
            {"t": 5.0, "bbox": [0.9, 0.9, 1.0, 1.0]},
        ],
        "key_frames": [{"t": 1.2, "score": 12.0, "bbox": [0.2, 0.3, 0.4, 0.5]}],
    }
    bbox, ts = pick_bbox_and_timestamp(det)
    assert bbox == [0.2, 0.3, 0.4, 0.5]
    assert ts == 1.2


def test_shape_hw_from_metadata_parses_height_width_lists():
    from shared.frame_shape import parse_metadata_hw

    assert parse_metadata_hw([1520, 2688]) == (1520, 2688)


def test_remap_skips_overlay_remap_when_bbox_already_playback_normalized():
    from record_hires_crop import remap_bbox_for_record_crop

    bbox = [0.25, 0.23, 0.41, 0.42]
    det = {
        "playback_timeline_synced": True,
        "detector_shape_hw": [704, 704],
        "overlay_shape_hw": [576, 704],
        "playback_shape_hw": [1520, 2688],
        "frames": [{"t": 5.0, "bbox": bbox}],
    }
    mapped = remap_bbox_for_record_crop(
        bbox,
        det,
        crop_shape_hw=(1520, 2688),
    )
    assert mapped == bbox


def test_remap_bbox_detect_overlay_to_main_playback_shape():
    from record_hires_crop import remap_bbox_for_record_crop

    bbox = [0.3, 0.35, 0.55, 0.65]
    det = {"frames": [{"t": 1.0, "bbox": bbox}]}
    mapped = remap_bbox_for_record_crop(
        bbox,
        det,
        crop_shape_hw=(1520, 2688),
        runtime_cfg={"processor.inference_lores_wh": [704, 576]},
    )
    assert mapped is not None
    assert mapped != bbox
    assert mapped[2] > mapped[0]
    assert mapped[3] > mapped[1]


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


def test_read_frame_ffmpeg_hw_helper_handles_missing_binary(monkeypatch):
    import record_hires_crop as rhc

    monkeypatch.setattr(rhc, "_ffmpeg_bin", lambda: None)
    assert rhc._read_frame_ffmpeg("/nope.mp4", 1.0, hwaccel=True) is None


def test_prefer_lores_explicit_skips_video_path():
    lores = np.zeros((16, 16, 3), dtype=np.uint8)
    det = {"best_frame": lores, "frames": [{"t": 1.0, "bbox": [0.1, 0.1, 0.2, 0.2]}]}
    crop, src = resolve_enrichment_crop(
        det,
        video_path="/would/seek.mp4",
        mode="record_hires",
        lores_crop=lores,
        prefer_lores=True,
    )
    assert src == "best_frame_lores"
    assert crop is lores


def test_record_hires_nvdec_defaults_on_for_jetson(monkeypatch):
    import record_hires_crop as rhc

    class _Cfg:
        def get(self, key, default=None):
            if key == "processor.record_hires_nvdec":
                return None
            if key == "video.encoding":
                return "jetson"
            return default

    import app_config.app_config as ac

    monkeypatch.setattr(ac, "app_config", _Cfg())
    assert rhc._record_hires_nvdec_enabled() is True


def test_record_hires_nvdec_can_disable(monkeypatch):
    import record_hires_crop as rhc
    import app_config.app_config as ac

    class _Cfg:
        def get(self, key, default=None):
            if key == "processor.record_hires_nvdec":
                return False
            return default

    monkeypatch.setattr(ac, "app_config", _Cfg())
    assert rhc._record_hires_nvdec_enabled() is False
