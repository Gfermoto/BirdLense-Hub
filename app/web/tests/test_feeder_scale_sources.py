"""Feeder scale sources: ESPHome direct and MQTT-backed normalization."""

from __future__ import annotations

from unittest.mock import patch

import services.feeder_scale as fs


class _Resp:
    def __init__(self, body: dict, status_code: int = 200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise fs.requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._body


def _cfg_get(overrides: dict):
    def get(key, default=None):
        return overrides[key] if key in overrides else default

    return get


def test_scale_tare_available_for_esphome():
    g = _cfg_get(
        {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "esphome",
            "integrations.scales.esphome_url": "http://scale.local",
            "integrations.scales.esphome_tare_button_id": "manual_tare",
        }
    )
    with patch.object(fs.app_config, "get", side_effect=g):
        assert fs.scale_tare_available() is True


def test_trigger_scale_tare_esphome_posts_button(monkeypatch):
    seen: list[str] = []

    def fake_post(url, timeout):
        seen.append(url)
        return _Resp({}, 200)

    g = _cfg_get(
        {
            "integrations.scales.source": "esphome",
            "integrations.scales.esphome_url": "http://scale.local/",
            "integrations.scales.esphome_tare_button_id": "manual_tare",
        }
    )
    monkeypatch.setattr(fs.requests, "post", fake_post)
    with patch.object(fs.app_config, "get", side_effect=g):
        ok, msg = fs.trigger_scale_tare()
    assert ok is True
    assert msg == "ok"
    assert seen == ["http://scale.local/button/manual_tare/press"]


def test_get_feeder_scale_snapshot_esphome_reads_weight_and_bird_present(
    monkeypatch,
):
    def fake_get(url, timeout):
        if url.endswith("/sensor/weight_live_internal"):
            return _Resp({"state": "12.34", "unit_of_measurement": "g"})
        if url.endswith("/binary_sensor/bird_present"):
            return _Resp({"state": "ON"})
        raise AssertionError(url)

    g = _cfg_get(
        {
            "integrations.scales.enabled": True,
            "integrations.scales.source": "esphome",
            "integrations.scales.esphome_url": "http://scale.local",
            "integrations.scales.esphome_weight_sensor_id": "weight_live_internal",
            "integrations.scales.esphome_bird_present_sensor_id": ("bird_present"),
            "integrations.scales.unit": "g",
        }
    )
    monkeypatch.setattr(fs.requests, "get", fake_get)
    with patch.object(fs.app_config, "get", side_effect=g):
        snap = fs.get_feeder_scale_snapshot()
    assert snap is not None
    assert snap["source"] == "esphome"
    assert snap["weight"] == 12.34
    assert snap["bird_present"] is True
    assert snap["unit"] == "g"
