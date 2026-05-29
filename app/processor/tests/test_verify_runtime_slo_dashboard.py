from scripts.verify_runtime_slo_dashboard import verify_report


def test_verify_runtime_slo_dashboard_passes():
    payload = {
        "slo_dashboard": {
            "schema": "runtime_slo_dashboard@v1",
            "snapshot": {
                "sustained_fps_avg_24h": 8.1,
                "skipped_ratio_avg_24h": 0.02,
                "pipeline_latency_p95_ms_24h": 1200.0,
                "per_camera_warn_count_24h": 0,
            },
            "status": {
                "ok": True,
                "breaches": [],
            },
        }
    }
    ok, errors = verify_report(
        payload,
        min_sustained_fps=7.0,
        max_skipped_ratio=0.05,
        max_latency_p95_ms=2500.0,
        max_per_camera_warn=0,
    )
    assert ok is True
    assert errors == []


def test_verify_runtime_slo_dashboard_fails():
    payload = {
        "slo_dashboard": {
            "schema": "runtime_slo_dashboard@v1",
            "snapshot": {
                "sustained_fps_avg_24h": 4.5,
                "skipped_ratio_avg_24h": 0.18,
                "pipeline_latency_p95_ms_24h": 4100.0,
                "per_camera_warn_count_24h": 2,
            },
            "status": {
                "ok": False,
                "breaches": ["sustained_fps_floor", "pipeline_latency_p95"],
            },
        }
    }
    ok, errors = verify_report(
        payload,
        min_sustained_fps=7.0,
        max_skipped_ratio=0.05,
        max_latency_p95_ms=2500.0,
        max_per_camera_warn=0,
    )
    assert ok is False
    assert any("sustained_fps_avg_24h" in err for err in errors)
    assert any("skipped_ratio_avg_24h" in err for err in errors)
    assert any("pipeline_latency_p95_ms_24h" in err for err in errors)
    assert any("per_camera_warn_count_24h" in err for err in errors)
