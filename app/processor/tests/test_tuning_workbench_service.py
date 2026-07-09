from services.system_tuning_workbench_service import (
    _PRESET_OVERRIDES,
    _collect_guardrail_feedback,
    _estimate_profile_metrics,
    _profile_delta,
    _runtime_cost_guard_error,
    _to_nested_patch,
)


def test_tuning_workbench_metrics_shift_with_thresholds():
    base = _estimate_profile_metrics(
        {
            "min_confidence_binary": 0.16,
            "min_confidence_to_process": 0.12,
            "min_track_duration": 0.75,
            "min_box_size_px": 14,
            "binary_imgsz": 704,
            "light_gate_enabled": True,
        }
    )
    recall = _estimate_profile_metrics(
        {
            "min_confidence_binary": 0.1,
            "min_confidence_to_process": 0.08,
            "min_track_duration": 0.5,
            "min_box_size_px": 12,
            "binary_imgsz": 640,
            "light_gate_enabled": False,
        }
    )
    assert recall["estimated_recall"] > base["estimated_recall"]
    assert recall["estimated_precision"] < base["estimated_precision"]


def test_tuning_workbench_guardrails_detect_risky_combo():
    fb = _collect_guardrail_feedback(
        {
            "min_confidence_binary": 0.09,
            "min_confidence_to_process": 0.07,
            "min_track_duration": 0.35,
            "min_box_size_px": 10,
            "binary_imgsz": 960,
            "light_gate_enabled": False,
        }
    )
    assert fb["errors"] == []
    assert len(fb["warnings"]) >= 2


def test_tuning_workbench_patch_helpers():
    patch = _to_nested_patch(
        {
            "processor.min_confidence_binary": 0.2,
            "processor.camera_overrides.BirdBox.min_box_size_px": 12,
        }
    )
    assert patch["processor"]["min_confidence_binary"] == 0.2
    assert (
        patch["processor"]["camera_overrides"]["BirdBox"]["min_box_size_px"]
        == 12
    )

    delta = _profile_delta(
        {
            "estimated_recall": 60.0,
            "estimated_precision": 70.0,
            "estimated_runtime_cost": 40.0,
        },
        {
            "estimated_recall": 63.0,
            "estimated_precision": 66.0,
            "estimated_runtime_cost": 45.0,
        },
    )
    assert delta == {
        "recall_delta": 3.0,
        "precision_delta": -4.0,
        "runtime_cost_delta": 5.0,
    }


def test_feeder_closeup_preset_exists():
    assert "feeder_closeup_ab" in _PRESET_OVERRIDES


def test_runtime_cost_guard_error():
    auto_eval = {"delta": {"runtime_cost_delta": 6.5}}
    err = _runtime_cost_guard_error(
        auto_eval,
        max_runtime_cost_delta=5.0,
    )
    assert isinstance(err, str) and "Rollback guard triggered" in err
    assert (
        _runtime_cost_guard_error(
            auto_eval,
            max_runtime_cost_delta=7.0,
        )
        is None
    )
