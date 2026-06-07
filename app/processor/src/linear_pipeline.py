"""Linear recording pipeline — strict stage order, helpers never veto core track persist.

Stages:
  1. trigger      (motion / MQTT — recording_session)
  2. detect_track (YOLO binary + ByteTrack — frame_processor, live)
  3. classify     (Birder + MQTT helpers — enrich species at finalize)
  4. reid_behavior (optional — after classify, before DB)
  5. persist      (create_video)
"""

from __future__ import annotations

import logging
from typing import Any

from object_confirm import track_object_confirmed
from persist_mode import binary_track_first_min_detector_conf, track_has_bbox_frames
from processor_config_defaults import (
    BIRDER_EU_MIN_CONFIDENCE,
    CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    PIPELINE_MODE,
    config_float,
)
from app_config.visit_eligibility import GENERIC_BIRD_SPECIES, visit_eligible_for_named_species
from runtime_contract import apply_runtime_contract

logger = logging.getLogger(__name__)

STAGE_TRIGGER = "trigger"
STAGE_DETECT_TRACK = "detect_track"
STAGE_CLASSIFY_ENRICH = "classify_enrich"
STAGE_REID_BEHAVIOR = "reid_behavior"
STAGE_PERSIST = "persist"


def pipeline_mode(app_config) -> str:
    return str(app_config.get("processor.pipeline_mode") or PIPELINE_MODE).strip().lower()


def is_linear_pipeline(app_config) -> bool:
    return pipeline_mode(app_config) in {"linear", "simple"}


def linear_disable_live_quality_gates(app_config) -> bool:
    """Linear core NVR: no static/scoring veto on live bird boxes."""
    return is_linear_pipeline(app_config)


def linear_skip_legacy_fusion_safeguards(app_config) -> bool:
    """Linear mode: no salvage / core-anchor / post-fusion second-guessing."""
    return is_linear_pipeline(app_config)


def linear_skip_frigate_salvage_paths(app_config) -> bool:
    """Linear: no Frigate standalone/salvage rows — core path is Hub YOLO track."""
    return is_linear_pipeline(app_config)


def _unknown_species_labels(app_config) -> set[str]:
    raw = str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird").strip().lower()
    return {"bird", "unknown", raw, "unknown bird"}


def _best_detector(track: dict[str, Any]) -> tuple[str, float, int] | None:
    events = track.get("detector_events") or []
    if not events:
        return None
    best_label = ""
    best_conf = -1.0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        label = str(ev.get("label") or "").strip()
        if not label:
            continue
        try:
            conf = float(ev.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf > best_conf:
            best_conf = conf
            best_label = label
    if not best_label:
        return None
    return best_label, max(0.0, best_conf), len(events)


def _species_from_classifier(
    app_config, track: dict[str, Any]
) -> tuple[str | None, float, bool, dict[str, Any] | None]:
    """Pick species from Birder events. Returns species=None when only detector evidence."""
    unknown = _unknown_species_labels(app_config)
    min_guess = config_float(
        app_config,
        "processor.classifier_best_guess_min_confidence",
        CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    )
    birder_min = config_float(
        app_config,
        "processor.birder_eu_min_confidence",
        BIRDER_EU_MIN_CONFIDENCE,
    )

    by_name: dict[str, list[dict[str, Any]]] = {}
    for ev in track.get("classifier_events") or []:
        if not isinstance(ev, dict):
            continue
        name = str(ev.get("species_name") or "").strip()
        if not name or name.lower() in unknown:
            continue
        by_name.setdefault(name, []).append(ev)

    if not by_name:
        return None, 0.0, True, None

    def _score(name: str) -> tuple[int, float]:
        rows = by_name[name]
        confs = [float(r.get("confidence") or 0.0) for r in rows]
        return (len(rows), sum(confs) / len(confs))

    best_name = max(by_name.keys(), key=_score)
    rows = by_name[best_name]
    avg_cls = sum(float(r.get("confidence") or 0.0) for r in rows) / len(rows)
    avg_combined = sum(float(r.get("combined_confidence") or 0.0) for r in rows) / len(rows)
    meta = {
        "species_name": best_name,
        "event_count": len(rows),
        "vote_share": len(rows) / max(1, len(track.get("classifier_events") or [])),
        "avg_classifier_confidence": avg_cls,
        "combined_confidence": avg_combined,
        "avg_entropy": None,
        "avg_top1_top2_margin": None,
    }
    if avg_cls < min_guess:
        return None, avg_cls, True, meta
    needs_review = avg_cls < birder_min
    return best_name, max(avg_combined, avg_cls), needs_review, meta


def evaluate_track_linear(
    *,
    app_config,
    track: dict[str, Any],
    min_track_duration: float,
    min_confidence_to_process: float,
) -> dict[str, Any]:
    """Stage detect_track → persist decision. No static_pinned / store_floor / arbiter."""
    try:
        dur = float(track["end_time"]) - float(track["start_time"])
    except (TypeError, ValueError, KeyError):
        dur = 0.0

    det = _best_detector(track)
    if det is None:
        return {
            "accepted": False,
            "decision_reason": "rejected_missing_detector_candidate",
            "decision_kind": "rejected",
            "reject_reason_code": "insufficient_frames",
            "detector_label": "",
            "detector_conf": 0.0,
            "detector_event_count": 0,
            "out_species": "Bird",
            "out_conf": 0.0,
            "visit_eligible": False,
            "notification_eligible": False,
            "evidence_state": "detector_only",
            "classifier_needs_review": False,
            "classifier_candidate": None,
        }

    detector_label, detector_conf, det_count = det
    if dur < float(min_track_duration):
        return _reject_linear(
            "rejected_short_track",
            "insufficient_frames",
            detector_label,
            detector_conf,
            det_count,
        )
    if str(detector_label).strip().lower() != "bird":
        return _reject_linear(
            "rejected_non_bird",
            "insufficient_frames",
            detector_label,
            detector_conf,
            det_count,
        )
    if not track_has_bbox_frames(track):
        return _reject_linear(
            "rejected_no_bbox",
            "insufficient_frames",
            detector_label,
            detector_conf,
            det_count,
        )

    floor = binary_track_first_min_detector_conf(app_config, float(min_confidence_to_process))
    confirmed, confirm_score, confirm_reason = track_object_confirmed(
        app_config=app_config,
        track=track,
        min_confidence_to_process=float(min_confidence_to_process),
    )
    if not confirmed and float(detector_conf) < floor:
        return _reject_linear(
            "rejected_detector_below_binary_floor",
            "low_confidence",
            detector_label,
            detector_conf,
            det_count,
        )
    if not confirmed:
        return _reject_linear(
            "rejected_object_not_confirmed",
            "low_confidence",
            detector_label,
            confirm_score,
            det_count,
        )

    detector_conf = max(float(detector_conf), float(confirm_score))

    species, sp_conf, needs_review, clf_meta = _species_from_classifier(app_config, track)
    if species is None:
        species = GENERIC_BIRD_SPECIES
        sp_conf = 0.0
        needs_review = True
        evidence_state = "detector_only"
        decision_reason = "accepted_binary_track_classifier_deferred"
    elif needs_review:
        evidence_state = "weak_classifier"
        decision_reason = "accepted_binary_track_classifier_uncertain"
    else:
        evidence_state = "species_supported"
        decision_reason = "accepted_species"
    out_conf = max(float(detector_conf), float(sp_conf))
    visit_ok = visit_eligible_for_named_species(species_name=species, visit_eligible=True)
    return {
        "accepted": True,
        "decision_reason": decision_reason,
        "decision_kind": "accepted_species",
        "reject_reason_code": None,
        "detector_label": detector_label,
        "detector_conf": detector_conf,
        "detector_event_count": det_count,
        "out_species": species,
        "out_conf": out_conf,
        "visit_eligible": visit_ok,
        "notification_eligible": not needs_review and visit_ok and species != GENERIC_BIRD_SPECIES,
        "evidence_state": evidence_state,
        "classifier_needs_review": needs_review,
        "classifier_candidate": clf_meta,
    }


def _reject_linear(
    reason: str,
    code: str,
    detector_label: str,
    detector_conf: float,
    det_count: int,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "decision_reason": reason,
        "decision_kind": "rejected",
        "reject_reason_code": code,
        "detector_label": detector_label,
        "detector_conf": detector_conf,
        "detector_event_count": det_count,
        "out_species": detector_label or "Bird",
        "out_conf": float(detector_conf),
        "visit_eligible": False,
        "notification_eligible": False,
        "evidence_state": "detector_only",
        "classifier_needs_review": False,
        "classifier_candidate": None,
    }


def build_linear_decisions(decision_maker, tracks: dict, app_config) -> list[dict[str, Any]]:
    """Build decision rows for linear pipeline (stage detect_track output)."""
    from decision_maker import _classifier_needs_review_flag, _parse_optional_threshold

    decisions: list[dict[str, Any]] = []
    entropy_ge = _parse_optional_threshold(app_config.get("processor.classifier_uncertainty_entropy_ge"))
    margin_le = _parse_optional_threshold(app_config.get("processor.classifier_uncertainty_margin_le"))

    for track_id, track in tracks.items():
        if not track.get("detector_events"):
            continue
        ev = evaluate_track_linear(
            app_config=app_config,
            track=track,
            min_track_duration=float(decision_maker.min_track_duration),
            min_confidence_to_process=float(decision_maker.min_confidence_to_process),
        )
        clf = ev.get("classifier_candidate")
        clf_entropy = clf.get("avg_entropy") if isinstance(clf, dict) else None
        clf_margin = clf.get("avg_top1_top2_margin") if isinstance(clf, dict) else None
        clf_needs = _classifier_needs_review_flag(clf_entropy, clf_margin, entropy_ge, margin_le)
        accepted = bool(ev["accepted"])
        decision_reason = str(ev["decision_reason"])
        reject_code = ev.get("reject_reason_code")

        decisions.append(
            apply_runtime_contract(
                {
                    "track_id": track_id,
                    "accepted": accepted,
                    "outcome_bucket": decision_maker._outcome_bucket(
                        accepted=accepted,
                        visit_eligible=bool(ev["visit_eligible"]),
                        decision_kind=str(ev["decision_kind"]),
                    ),
                    "visit_eligible": bool(ev["visit_eligible"]),
                    "notification_eligible": bool(ev["notification_eligible"]),
                    "species_name": ev["out_species"],
                    "start_time": track["start_time"],
                    "end_time": track["end_time"],
                    "confidence": float(ev["out_conf"]),
                    "best_frame": track.get("best_frame"),
                    "best_frame_score": float(track.get("best_frame_score") or 0.0),
                    "key_frame_count": len(track.get("key_frames") or []),
                    "source": "video",
                    "detection_provider": "yolo",
                    "frames": track.get("frames", []),
                    "decision_reason": decision_reason,
                    "detector_label": ev["detector_label"],
                    "detector_confidence": float(ev["detector_conf"]),
                    "detector_event_count": int(ev["detector_event_count"]),
                    "classifier_threshold": None,
                    "classifier_species_name": clf.get("species_name") if isinstance(clf, dict) else None,
                    "classifier_confidence": clf.get("combined_confidence") if isinstance(clf, dict) else None,
                    "classifier_event_count": int(clf.get("event_count") or 0) if isinstance(clf, dict) else 0,
                    "classifier_vote_share": float(clf.get("vote_share") or 0.0) if isinstance(clf, dict) else 0.0,
                    "classifier_entropy": clf_entropy,
                    "classifier_top1_top2_margin": clf_margin,
                    "classifier_needs_review": bool(ev["classifier_needs_review"]) or clf_needs,
                    "decision_kind": str(ev["decision_kind"]),
                    "reject_reason_code": reject_code,
                    "evidence_state": str(ev["evidence_state"]),
                    "trust_band": decision_maker._trust_band_for_decision(
                        accepted, decision_reason, float(ev["out_conf"]), reject_code
                    ),
                    "pipeline_stage": STAGE_DETECT_TRACK,
                }
            )
        )

    decisions.sort(
        key=lambda item: (
            int(not item.get("accepted", False)),
            -float(item.get("confidence") or 0.0),
            int(item.get("track_id") or 0),
        )
    )
    return decisions
