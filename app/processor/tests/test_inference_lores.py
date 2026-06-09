"""Tests for native detect-stream lores resolution."""

from inference_lores import (
    parse_inference_lores_wh,
    resolve_inference_lores_size,
    resolve_track_regen_lores_size,
)


def test_parse_inference_lores_wh_list():
    assert parse_inference_lores_wh([704, 576]) == (704, 576)


def test_resolve_inference_lores_wh_overrides_square_px():
    cfg = {
        "processor.inference_lores_wh": [704, 576],
        "processor.inference_lores_px": 640,
    }
    assert resolve_inference_lores_size(cfg) == (704, 576)


def test_resolve_inference_lores_px_fallback():
    cfg = {"processor.inference_lores_px": 640}
    assert resolve_inference_lores_size(cfg) == (640, 640)


def test_resolve_inference_lores_ignores_video_dimensions():
    cfg = {"video.video_width": 704, "video.video_height": 576}
    assert resolve_inference_lores_size(cfg) is None


def test_track_regen_lores_px_over_inference_wh():
    cfg = {
        "processor.track_regen_lores_px": 512,
        "processor.inference_lores_wh": [704, 576],
    }
    assert resolve_track_regen_lores_size(cfg) == (512, 512)


def test_track_regen_wh():
    cfg = {
        "processor.track_regen_lores_wh": [704, 576],
        "processor.inference_lores_px": 640,
    }
    assert resolve_track_regen_lores_size(cfg) == (704, 576)
