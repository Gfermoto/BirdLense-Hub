"""Post-fusion rejection accounting for finalized recordings."""

from __future__ import annotations

from typing import Any

from decision_outcome import compute_outcome_bucket


def _min_confidence_to_store(config: Any) -> float:
    try:
        return float(config.get("detection.min_confidence_to_store") or 0.05)
    except (TypeError, ValueError):
        return 0.05


def collect_post_fusion_rejections(
    config: Any,
    *,
    accepted_pre_fusion: list[dict],
    persisted_detections: list[dict],
) -> list[dict]:
    min_conf_store = _min_confidence_to_store(config)
    fused_ids = {
        detection.get("track_id") for detection in persisted_detections if detection.get("track_id") is not None
    }
    rejections: list[dict] = []
    for item in accepted_pre_fusion:
        track_id = item.get("track_id")
        if track_id is None or track_id in fused_ids:
            continue
        confidence = float(item.get("confidence") or 0.0)
        if confidence >= min_conf_store:
            continue
        rejections.append(
            {
                **item,
                "accepted": False,
                "decision_reason": "rejected_post_fusion_below_store_threshold",
                "decision_kind": "rejected",
                "outcome_bucket": compute_outcome_bucket(
                    accepted=False,
                    visit_eligible=bool(item.get("visit_eligible", True)),
                    decision_kind="rejected",
                ),
                "trust_band": "red",
                "reject_reason_code": "low_confidence",
            }
        )
    return rejections
