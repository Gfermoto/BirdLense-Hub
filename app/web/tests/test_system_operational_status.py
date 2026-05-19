"""Operational status helpers for System monitoring."""

from __future__ import annotations

from services.system_operational_status import (
    enrich_birdnet_fifo_response,
    filter_runtime_parity_alerts,
    resolve_birdnet_fifo_operational_status,
    strict_quality_ratio_ok,
)


def _get(key, default=None):
    cfg = {
        "mqtt.broker": "localhost",
        "mqtt.birdnet_topic": "",
        "processor.birdnet_fifo_snapshot_enabled": True,
        "processor.birdnet_fifo_persist_enabled": True,
        "triggers.frigate.enabled": False,
    }
    return cfg.get(key, default)


def test_birdnet_disabled_when_no_topic():
    status = resolve_birdnet_fifo_operational_status(
        app_config_get=_get,
        available=False,
        reason="snapshot_file_missing",
    )
    assert status["operational_tier"] == "info"
    assert status["operational_code"] == "birdnet_disabled"


def test_birdnet_empty_queue_is_info_not_critical():
    def get_on(key, default=None):
        return {
            "mqtt.broker": "x",
            "mqtt.birdnet_topic": "birdnet",
            "processor.birdnet_fifo_snapshot_enabled": True,
            "processor.birdnet_fifo_persist_enabled": True,
        }.get(key, default)

    status = resolve_birdnet_fifo_operational_status(
        app_config_get=get_on,
        available=True,
        queue_len=0,
    )
    assert status["operational_tier"] == "info"
    assert status["operational_code"] == "birdnet_queue_empty"


def test_enrich_birdnet_fifo_response_attaches_fields():
    body = enrich_birdnet_fifo_response(
        {"available": True, "snapshot": {"queue_len": 2, "fifo_cap": 1000}},
        app_config_get=lambda k, d=None: {
            "mqtt.broker": "h",
            "mqtt.birdnet_topic": "birdnet",
        }.get(k, d),
    )
    assert body["operational_tier"] == "ok"
    assert body["operational_code"] == "birdnet_active"


def test_strict_quality_ratio_skips_empty_sample():
    assert strict_quality_ratio_ok(None, sample_count=0, threshold=0.9) is True
    assert strict_quality_ratio_ok(0.5, sample_count=0, threshold=0.9) is True
    assert strict_quality_ratio_ok(0.5, sample_count=10, threshold=0.9) is False


def test_strict_quality_block_skips_ratio_without_24h_sample():
    from services.system_domain_health_service import _build_strict_quality_block

    block = _build_strict_quality_block(
        duplicate_video_groups=0,
        duplicate_detection_groups=0,
        duplicate_clip_candidates=[],
        species_sync_actions=[],
        detection_track_metrics={
            "video_detections_24h": 0,
            "video_detections_with_frames_ratio_24h": None,
            "video_detections_primary_yolo_ratio_24h": None,
        },
    )
    assert block["video_detections_with_frames_ratio_ok"] is True
    assert block["video_detections_primary_yolo_ratio_ok"] is True
    assert block["strict_quality_ready"] is True


def test_filter_frigate_parity_when_frigate_off():
    alerts = filter_runtime_parity_alerts(
        {
            "frigate_degraded_no_mqtt": True,
            "effective_trigger_paths_dropped": True,
        },
        app_config_get=lambda k, d=None: False if k == "triggers.frigate.enabled" else d,
    )
    assert alerts["frigate_degraded_no_mqtt"] is False
