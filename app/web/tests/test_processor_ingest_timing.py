"""Tests for processor video ingest timing (#586)."""

from services.processor_ingest.ingest_timing import IngestTimingRecorder, merge_ingest_timing_response


def test_ingest_timing_recorder_laps_and_total():
    timing = IngestTimingRecorder()
    timing.lap("parse_ms")
    timing.lap("prepare_ms")
    out = timing.finish()
    assert out["parse_ms"] >= 0.0
    assert out["prepare_ms"] >= 0.0
    assert out["total_ms"] >= out["parse_ms"]


def test_merge_ingest_timing_response():
    merged = merge_ingest_timing_response({"video_id": 1}, {"total_ms": 12.3})
    assert merged["video_id"] == 1
    assert merged["ingest_timing_ms"]["total_ms"] == 12.3
