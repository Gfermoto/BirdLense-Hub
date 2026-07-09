"""Unit tests for feeder scale video payload helpers."""

from services.feeder_scale import (
    _weight_trend_from_grams,
    video_scales_estimate_payload,
)


class _VideoStub:
    def __init__(self, kg):
        self.scales_weight_delta_kg = kg


def test_weight_trend_thresholds():
    assert _weight_trend_from_grams(0) == "stable"
    assert _weight_trend_from_grams(5) == "stable"
    assert _weight_trend_from_grams(5.1) == "up"
    assert _weight_trend_from_grams(-5) == "stable"
    assert _weight_trend_from_grams(-5.1) == "down"


def test_video_scales_payload_signed_grams():
    payload = video_scales_estimate_payload(_VideoStub(0.012))
    assert payload is not None
    assert payload["weight_change_grams"] == 12.0
    assert payload["weight_trend"] == "up"
    assert payload["display_value"] == 12.0

    down = video_scales_estimate_payload(_VideoStub(-0.008))
    assert down is not None
    assert down["weight_change_grams"] == -8.0
    assert down["weight_trend"] == "down"

    flat = video_scales_estimate_payload(_VideoStub(0.003))
    assert flat is not None
    assert flat["weight_trend"] == "stable"
