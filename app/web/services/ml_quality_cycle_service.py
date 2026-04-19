"""Review -> calibration -> retrain readiness report for Hub ML loop."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone

from services.detection_quality_baseline_service import (
    build_detection_quality_baseline,
)


def _read_json(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _dataset_quality_gate(dataset_info: dict | None) -> tuple[bool, bool]:
    if not isinstance(dataset_info, dict):
        return False, False
    split_params = dataset_info.get("split_params") or {}
    quality = dataset_info.get("quality") or {}
    ready = bool(split_params.get("ready_for_train"))
    strict_requested = bool(split_params.get("strict_quality"))
    duplicates = int(quality.get("duplicate_track_count") or 0)
    video_leakage = quality.get("video_leakage") or {}
    group_leakage = quality.get("group_leakage") or {}
    leakage = sum(
        int(video_leakage.get(k) or 0) + int(group_leakage.get(k) or 0)
        for k in ("train_val_shared", "train_test_shared", "val_test_shared")
    )
    return ready, strict_requested and duplicates == 0 and leakage == 0


def build_review_retrain_cycle_report(
    *,
    days: int = 14,
    dataset_info_path: str | None = None,
    fusion_eval_report_path: str | None = None,
    runtime_snapshot: Mapping[str, object] | None = None,
) -> dict:
    """Combine baseline, dataset export quality and fusion eval presence."""
    dataset_info = _read_json(dataset_info_path)
    baseline = build_detection_quality_baseline(
        days=days,
        runtime_snapshot=runtime_snapshot,
    )
    dataset_ready, dataset_quality_ok = _dataset_quality_gate(dataset_info)
    fusion_eval_present = bool(fusion_eval_report_path and os.path.isfile(fusion_eval_report_path))
    runtime_present = bool(runtime_snapshot)

    recommendations: list[str] = []
    if not dataset_ready:
        recommendations.append("Собрать новый dataset export с ready_for_train=true.")
    if not dataset_quality_ok:
        recommendations.append("Починить leakage/duplicate tracks до retrain.")
    if not fusion_eval_present:
        recommendations.append("Сначала прогнать fusion eval report на свежем training CSV.")
    if baseline["correction_proxies"].get("species_change_actions", 0) == 0:
        recommendations.append("Недостаточно ручных corrections: retrain без review-сигнала будет слепым.")
    if not runtime_present:
        recommendations.append("Нет runtime snapshot процессора: трудно сравнивать latency до/после retrain.")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "dataset_info_path": dataset_info_path,
            "fusion_eval_report_path": fusion_eval_report_path,
            "runtime_snapshot_present": runtime_present,
        },
        "baseline": baseline,
        "gates": {
            "dataset_ready_for_train": dataset_ready,
            "dataset_strict_quality_ok": dataset_quality_ok,
            "fusion_eval_present": fusion_eval_present,
            "runtime_observability_present": runtime_present,
        },
        "recommendations": recommendations,
    }
