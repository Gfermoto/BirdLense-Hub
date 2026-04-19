import json


def test_build_processor_runtime_snapshot_response_reads_snapshot(app, monkeypatch, tmp_path):
    from services.system_diagnostics_service import (
        build_processor_runtime_snapshot_response,
    )

    diag = tmp_path / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    snapshot_path = diag / "processor_runtime_stats.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "counters": {"mqtt_outbound_drops_total": 2},
                "gauges": {"mqtt_outbound_queue_depth": 5},
                "latency_ms": {"frame_processor_detect_p95": 44.0},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("services.system_diagnostics_service.data_paths.data_dir", lambda: str(tmp_path))

    with app.app_context():
        body, code = build_processor_runtime_snapshot_response()

    assert code == 200
    assert body["available"] is True
    assert body["snapshot"]["counters"]["mqtt_outbound_drops_total"] == 2
    assert body["snapshot"]["latency_ms"]["frame_processor_detect_p95"] == 44.0
