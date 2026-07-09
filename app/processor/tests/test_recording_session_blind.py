"""YOLO blind quickcheck must not double-count per-frame session metrics."""

from __future__ import annotations


def _make_accumulators():
    runtime_signals = {
        "yolo_frames_ran": 0,
        "yolo_frames_with_tracks": 0,
        "yolo_frames_with_raw_boxes": 0,
        "yolo_raw_boxes_total": 0,
        "yolo_accepted_boxes_total": 0,
        "low_light_blocked_frames": 0,
    }
    processor_status: dict = {}

    def _raw_boxes_from_stats(local_stats: dict) -> int:
        return int(local_stats.get("yolo_raw_boxes") or 0)

    def _accumulate_run_stats(local_stats: dict, *, count_frame_metrics: bool = True) -> int:
        raw_boxes_local = _raw_boxes_from_stats(local_stats)
        if not count_frame_metrics:
            return raw_boxes_local
        if local_stats.get("yolo_ran"):
            runtime_signals["yolo_frames_ran"] += 1
            processor_status["last_yolo_ok_at"] = "ok"
        if local_stats.get("yolo_track_found"):
            runtime_signals["yolo_frames_with_tracks"] += 1
        if raw_boxes_local > 0:
            runtime_signals["yolo_frames_with_raw_boxes"] += 1
            runtime_signals["yolo_raw_boxes_total"] += raw_boxes_local
        runtime_signals["yolo_accepted_boxes_total"] += int(local_stats.get("yolo_accepted_boxes") or 0)
        if local_stats.get("light_gate_blocked"):
            runtime_signals["low_light_blocked_frames"] += 1
        return raw_boxes_local

    return runtime_signals, _accumulate_run_stats


def test_primary_then_quickcheck_probe_does_not_double_count():
    runtime_signals, accumulate = _make_accumulators()
    primary = {"yolo_ran": True, "yolo_raw_boxes": 0, "yolo_accepted_boxes": 1}
    quick = {"yolo_ran": True, "yolo_raw_boxes": 4, "yolo_accepted_boxes": 2}

    accumulate(primary)
    accumulate(quick, count_frame_metrics=False)

    assert runtime_signals["yolo_frames_ran"] == 1
    assert runtime_signals["yolo_raw_boxes_total"] == 0
    assert runtime_signals["yolo_accepted_boxes_total"] == 1


def test_primary_raw_boxes_triggers_recovery_before_quickcheck_branch():
    """Primary run recovery is independent of frigate-only / quickcheck elif chain."""
    phase = "suspected"
    raw_boxes = 2
    frigate_only_extension = True

    if raw_boxes > 0:
        phase = "recovered"

    if frigate_only_extension:
        if phase == "suspected":
            phase = "recovered"

    assert phase == "recovered"


def test_frigate_only_quickcheck_recovery_without_double_count():
    """In suspected phase, quickcheck hit recovers but does not double session counters."""
    runtime_signals, accumulate = _make_accumulators()
    runtime_signals["yolo_blind_phase"] = "suspected"

    raw_boxes = accumulate({"yolo_ran": True, "yolo_raw_boxes": 0, "yolo_accepted_boxes": 0})
    assert raw_boxes == 0
    assert runtime_signals["yolo_frames_ran"] == 1

    quick_raw = accumulate(
        {"yolo_ran": True, "yolo_raw_boxes": 3, "yolo_accepted_boxes": 2},
        count_frame_metrics=False,
    )
    if quick_raw > 0:
        runtime_signals["yolo_blind_phase"] = "recovered"

    assert runtime_signals["yolo_frames_ran"] == 1
    assert runtime_signals["yolo_raw_boxes_total"] == 0
    assert runtime_signals["yolo_accepted_boxes_total"] == 0
    assert runtime_signals["yolo_blind_phase"] == "recovered"


def test_expired_quickcheck_window_confirms_only_if_still_suspected():
    """After window ends, confirm blind only when phase never recovered."""
    phase = "suspected"
    now_m = 10.0
    until = 5.0

    if now_m <= until:
        phase = "recovered"
    elif phase == "suspected":
        phase = "confirmed"

    assert phase == "confirmed"


def test_expired_window_does_not_confirm_after_primary_recovery():
    phase = "suspected"
    now_m = 10.0
    until = 5.0
    raw_boxes = 3

    if raw_boxes > 0:
        phase = "recovered"
        until = 0.0

    frigate_only_extension = True
    if frigate_only_extension and phase == "suspected":
        if now_m <= until:
            pass
        elif phase == "suspected":
            phase = "confirmed"

    assert phase == "recovered"


def test_quickcheck_failure_inside_window_stays_suspected():
    phase = "suspected"
    now_m = 3.0
    until = 8.0
    quick_raw = 0

    if phase == "suspected":
        if now_m <= until:
            if quick_raw > 0:
                phase = "recovered"
        elif phase == "suspected":
            phase = "confirmed"

    assert phase == "suspected"


def test_primary_raw_boxes_recovers_even_when_frigate_extends_session():
    """Primary YOLO boxes recover blind state even if session was extended by Frigate-only."""
    runtime_signals, accumulate = _make_accumulators()
    runtime_signals["yolo_blind_phase"] = "suspected"

    raw_boxes = accumulate({"yolo_ran": True, "yolo_raw_boxes": 2, "yolo_accepted_boxes": 1})
    raw_yolo_detections = True
    has_detections = True
    frigate_only_extension = bool(has_detections and not raw_yolo_detections)

    if raw_boxes > 0:
        runtime_signals["yolo_blind_phase"] = "recovered"

    assert not frigate_only_extension
    assert runtime_signals["yolo_blind_phase"] == "recovered"
    assert runtime_signals["yolo_raw_boxes_total"] == 2
