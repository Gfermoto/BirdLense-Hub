import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)


def test_runtime_stats_snapshot_persists_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    import processor_runtime_stats as prs

    prs.reset_runtime_stats_for_tests()
    prs.inc_counter("mqtt_outbound_drops_total")
    prs.set_gauge("mqtt_outbound_queue_depth", 7)
    prs.observe_timing("frame_processor_detect", 24.0)
    prs.observe_timing("frame_processor_detect", 55.0)
    path = prs.flush_runtime_stats_snapshot(force=True)

    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["counters"]["mqtt_outbound_drops_total"] == 1
    assert body["gauges"]["mqtt_outbound_queue_depth"] == 7
    assert body["latency_ms"]["frame_processor_detect_count"] == 2
    assert body["latency_ms"]["frame_processor_detect_p95"] == 55.0


def test_runtime_stats_large_disk_style_gauge_serializes(tmp_path, monkeypatch):
    """Гигабайтные счётчики диска остаются целыми в JSON (#340)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    import processor_runtime_stats as prs

    prs.reset_runtime_stats_for_tests()
    hundred_gib = 100 * 1024**3
    prs.set_gauge("recording_disk_bytes_used", hundred_gib)
    path = prs.flush_runtime_stats_snapshot(force=True)
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["gauges"]["recording_disk_bytes_used"] == hundred_gib


def test_observe_timing_maxlen_keeps_last_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    import processor_runtime_stats as prs

    prs.reset_runtime_stats_for_tests()
    for i in range(250):
        prs.observe_timing("frame_processor_detect", float(i))
    snap = prs.runtime_stats_snapshot()
    assert snap["latency_ms"]["frame_processor_detect_count"] == 200
    assert snap["latency_ms"]["frame_processor_detect_last"] == 249.0


def test_observe_timing_ignores_negative(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    import processor_runtime_stats as prs

    prs.reset_runtime_stats_for_tests()
    prs.observe_timing("x", -5.0)
    assert "x_count" not in prs.runtime_stats_snapshot()["latency_ms"]


def test_runtime_stats_write_failure_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    import processor_runtime_stats as prs

    prs.reset_runtime_stats_for_tests()
    monkeypatch.setattr(prs.os, "replace", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))

    prs.inc_counter("safe_even_when_snapshot_write_fails")

    assert prs.runtime_stats_snapshot()["counters"]["safe_even_when_snapshot_write_fails"] == 1
