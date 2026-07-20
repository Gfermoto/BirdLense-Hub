"""Linear recording pipeline — strict stage order, helpers never veto core track persist.

Stages:
  1. trigger      (motion / MQTT — recording_session)
  2. detect_track (YOLO binary + ByteTrack — frame_processor, live)
  3. classify     (Birder + MQTT helpers — enrich species at finalize)
  4. arbitrate    (decision_maker — accept/reject tracks)
  5. reid_enrich  (optional — after classify, before DB)
  6. welfare_enrich (optional — Mahalanobis screening, after reid)
  7. persist      (create_video)
"""

from __future__ import annotations

import logging
from typing import Any

from object_confirm import track_object_confirmed
from persist_mode import (
    binary_track_first_min_detector_conf,
    defer_static_pinned_reject,
    track_has_bbox_frames,
)
from processor_config_defaults import (
    BIRDER_EU_MIN_CONFIDENCE,
    CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    config_float,
)
from app_config.visit_eligibility import GENERIC_BIRD_SPECIES, visit_eligible_for_named_species
from camera_tuning_roles import role_preset as _role_preset
from pipeline_mode_utils import is_linear_pipeline
from recognition_outcome import stamp_recognition_outcome
from runtime_contract import track_id_sort_key
from runtime_contract import apply_runtime_contract

logger = logging.getLogger(__name__)

STAGE_TRIGGER = "trigger"
STAGE_DETECT_TRACK = "detect_track"
STAGE_CLASSIFY_ENRICH = "classify_enrich"
STAGE_REID_ENRICH = "reid_enrich"
STAGE_WELFARE_ENRICH = "welfare_enrich"
STAGE_PERSIST = "persist"


def frigate_salvage_opted_in(app_config, *, camera_id: str | None = None) -> bool:
    """Global or per-role opt-in for Frigate trigger review salvage (linear exception)."""
    if bool(app_config.get("detection.frigate_trigger_review_salvage_enabled", False)):
        return True
    preset = _role_preset(app_config, camera_id)
    raw = preset.get("frigate_trigger_review_salvage_enabled")
    return bool(raw) if raw is not None else False


def frigate_salvage_allow_without_yolo(app_config, *, camera_id: str | None = None) -> bool:
    if bool(app_config.get("detection.frigate_trigger_review_salvage_allow_without_yolo_tracks", False)):
        return True
    preset = _role_preset(app_config, camera_id)
    raw = preset.get("frigate_trigger_review_salvage_allow_without_yolo_tracks")
    return bool(raw) if raw is not None else False


def linear_skip_legacy_fusion_safeguards(app_config) -> bool:
    """Linear mode: skip legacy post-fusion veto, salvage persist, and anchor restore.

    Skipped when linear (standalone-first, ADR classifier-hints-only):
    - ``collect_post_fusion_rejections`` (second-guess accepted pre-fusion rows)
    - ``yolo_core_anchor_enabled`` forced False (no fusion-drop anchor restore)
    - ``restore_detect_first_persist_rows`` (detect-first persist bypass)
    - weak YOLO salvage and Frigate trigger salvage (opt-in via ``frigate_salvage_opted_in`` only)

    Still active in linear:
    - bbox contract, track_first gate, dual_stream_timeline remap
    - normal YOLO+ByteTrack persist through classify flow
    """
    return is_linear_pipeline(app_config)


def linear_skip_frigate_salvage_paths(app_config, *, camera_id: str | None = None) -> bool:
    """Linear: skip Frigate salvage unless global or ``camera_tuning_by_role`` opt-in.

    Standalone-first default: Frigate/BirdNET remain hints in fusion, not persist drivers.
    Frigate-site installs: set ``tuning_role: frigate_site`` or global
    ``detection.frigate_trigger_review_salvage_enabled: true``.
    """
    if not is_linear_pipeline(app_config):
        return False
    return not frigate_salvage_opted_in(app_config, camera_id=camera_id)


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

    raw_events = [ev for ev in (track.get("classifier_events") or []) if isinstance(ev, dict)]
    if not by_name:
        # Classifier ran but only Unknown / empty labels → open-set abstain (RC7).
        if raw_events:
            return None, 0.0, True, {
                "species_name": None,
                "event_count": len(raw_events),
                "vote_share": 0.0,
                "avg_classifier_confidence": 0.0,
                "combined_confidence": 0.0,
                "avg_entropy": None,
                "avg_top1_top2_margin": None,
                "abstain": "unknown",
            }
        return None, 0.0, True, None

    track_id = track.get("track_id", track.get("id"))
    adjust_fn = None
    data_dir = None
    try:
        from processor_support import get_data_dir
        from site_adapter import adjust_confidence_with_site_adapter

        adjust_fn = adjust_confidence_with_site_adapter
        data_dir = get_data_dir()
    except Exception:
        adjust_fn = None

    def _avg_conf(name: str) -> float:
        rows = by_name[name]
        confs = [float(r.get("confidence") or 0.0) for r in rows]
        return sum(confs) / len(confs)

    def _adjust(name: str) -> tuple[float, float, dict[str, Any]]:
        avg = _avg_conf(name)
        adj = avg
        info: dict[str, Any] = {"applied": False}
        if adjust_fn is not None and data_dir is not None:
            try:
                adj, info = adjust_fn(
                    data_dir=data_dir,
                    species=name,
                    confidence=avg,
                    track_id=track_id,
                )
                if not info.get("applied"):
                    adj = avg
            except Exception:
                adj = avg
                info = {"applied": False}
        return float(adj), avg, info

    def _invent_only(name: str) -> bool:
        rows = by_name[name]
        return bool(rows) and all(
            r.get("soft") and str(r.get("soft_reason") or "") == "prior_open_set_guess"
            for r in rows
        )

    def _score(name: str) -> tuple[int, float, int, float]:
        """Prefer real model mass over open-set invent; then prior-aware adj."""
        adj, avg, _info = _adjust(name)
        # invent_only=0 ranks above invent_only=1
        return (0 if _invent_only(name) else 1, adj, len(by_name[name]), avg)

    # Prior re-rank only (adj conf). No confuse-group / tiny-mass dove override —
    # those flipped true pigeon clips when long-tail dove got site prior.
    best_name = max(by_name.keys(), key=_score)
    rows = by_name[best_name]
    avg_cls = _avg_conf(best_name)
    avg_combined = sum(float(r.get("combined_confidence") or 0.0) for r in rows) / len(rows)
    soft_share = sum(1 for r in rows if r.get("soft")) / max(1, len(rows))
    # RC5 / Bet A: site-adapter species priors (canary) adjust classifier conf.
    adapter_info: dict[str, Any] = {"applied": False}
    if adjust_fn is not None and data_dir is not None:
        try:
            adj_cls, adapter_info = adjust_fn(
                data_dir=data_dir,
                species=best_name,
                confidence=avg_cls,
                track_id=track_id,
            )
            if adapter_info.get("applied"):
                avg_cls = adj_cls
                if avg_combined > 0:
                    avg_combined = max(
                        0.0,
                        min(1.0, avg_combined + float(adapter_info.get("delta") or 0.0)),
                    )
        except Exception:
            adapter_info = {"applied": False}
    meta = {
        "species_name": best_name,
        "event_count": len(rows),
        "vote_share": len(rows) / max(1, len(raw_events)),
        "avg_classifier_confidence": avg_cls,
        "combined_confidence": avg_combined,
        "avg_entropy": None,
        "avg_top1_top2_margin": None,
        "soft_share": soft_share,
    }
    if adapter_info.get("applied"):
        meta["site_adapter"] = adapter_info
        meta["prior_rerank"] = True
    if avg_cls < min_guess:
        meta["abstain"] = "low_conf"
        return None, avg_cls, True, meta
    invent_share = sum(
        1
        for r in rows
        if r.get("soft") and str(r.get("soft_reason") or "") == "prior_open_set_guess"
    ) / max(1, len(rows))
    needs_review = avg_cls < birder_min or soft_share >= 1.0 or invent_share > 0
    if invent_share >= 1.0:
        meta["invent_only"] = True
    return best_name, max(avg_combined, avg_cls), needs_review, meta


def evaluate_track_linear(
    *,
    app_config,
    track: dict[str, Any],
    min_track_duration: float,
    min_confidence_to_process: float,
    static_pinned_cfg: Any | None = None,
) -> dict[str, Any]:
    """Stage detect_track → persist decision. Optional static_pinned reject (#608)."""
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

    try:
        from track_geometry import StaticPinnedTrackConfig, static_pinned_track_reason

        raw = app_config.get("processor.linear_static_pinned_reject_enabled")
        static_enabled = True if raw is None else bool(raw)
        if static_enabled:
            static_cfg = static_pinned_cfg or StaticPinnedTrackConfig.from_runtime_cfg(app_config)
            if static_cfg.enabled:
                static_reason = static_pinned_track_reason(track, static_cfg)
                if static_reason and defer_static_pinned_reject(
                    app_config=app_config,
                    track=track,
                    detector_events=track.get("detector_events") or [],
                    min_confidence_to_process=float(min_confidence_to_process),
                ):
                    static_reason = None
                if static_reason:
                    return _reject_linear(
                        "rejected_static_pinned_track",
                        "insufficient_frames",
                        detector_label,
                        detector_conf,
                        det_count,
                    )
    except ImportError:
        pass

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
    from visit_contract import is_named_product_species

    birder_unknown = str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird")
    classify_skip_reason = track.get("classify_skip_reason")
    if isinstance(classify_skip_reason, str):
        classify_skip_reason = classify_skip_reason.strip() or None
    else:
        classify_skip_reason = None

    if species is None:
        species = GENERIC_BIRD_SPECIES
        sp_conf = 0.0
        needs_review = True
        evidence_state = "detector_only"
        decision_reason = "accepted_binary_track_classifier_deferred"
        abstain = (clf_meta or {}).get("abstain") if isinstance(clf_meta, dict) else None
        if not classify_skip_reason:
            if abstain == "unknown":
                classify_skip_reason = "unknown_abstain"
            elif abstain == "low_conf":
                classify_skip_reason = "low_conf"
            else:
                classify_skip_reason = "deferred"
    elif needs_review:
        evidence_state = "weak_classifier"
        decision_reason = "accepted_binary_track_classifier_uncertain"
    else:
        evidence_state = "species_supported"
        decision_reason = "accepted_species"

    # Visit contract: placeholder Bird/Unknown is review_only, not accepted_species win.
    # Uncertain named (best-guess band) is also review_only — never hub taxonomy win.
    named = is_named_product_species(species, birder_unknown_label=birder_unknown)
    visit_ok = visit_eligible_for_named_species(
        species_name=species,
        visit_eligible=True,
        birder_unknown_label=birder_unknown,
    )
    if not named:
        # Presence persist only — not a SpeciesVisit product win.
        decision_kind = "review_only_generic"
        visit_ok = False
        notification_eligible = False
    elif needs_review:
        decision_kind = "review_only_uncertain_species"
        visit_ok = False
        notification_eligible = False
    else:
        decision_kind = "accepted_species"
        notification_eligible = bool(visit_ok)

    out_conf = max(float(detector_conf), float(sp_conf))
    pipeline_stage = (
        STAGE_CLASSIFY_ENRICH
        if (isinstance(clf_meta, dict) and clf_meta.get("event_count")) or named
        else STAGE_DETECT_TRACK
    )
    return {
        "accepted": True,
        "decision_reason": decision_reason,
        "decision_kind": decision_kind,
        "reject_reason_code": None,
        "detector_label": detector_label,
        "detector_conf": detector_conf,
        "detector_event_count": det_count,
        "out_species": species,
        "out_conf": out_conf,
        "visit_eligible": visit_ok,
        "notification_eligible": notification_eligible,
        "evidence_state": evidence_state,
        "classifier_needs_review": needs_review or (not named),
        "classifier_candidate": clf_meta,
        "classify_skip_reason": classify_skip_reason,
        "pipeline_stage": pipeline_stage,
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
        "out_species": detector_label,
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

    static_pinned_cfg = decision_maker._resolve_static_pinned_cfg()

    for track_id, track in tracks.items():
        if not track.get("detector_events"):
            continue
        ev = evaluate_track_linear(
            app_config=app_config,
            track=track,
            min_track_duration=float(decision_maker.min_track_duration),
            min_confidence_to_process=float(decision_maker.min_confidence_to_process),
            static_pinned_cfg=static_pinned_cfg,
        )
        clf = ev.get("classifier_candidate")
        clf_entropy = clf.get("avg_entropy") if isinstance(clf, dict) else None
        clf_margin = clf.get("avg_top1_top2_margin") if isinstance(clf, dict) else None
        clf_needs = _classifier_needs_review_flag(clf_entropy, clf_margin, entropy_ge, margin_le)
        accepted = bool(ev["accepted"])
        decision_reason = str(ev["decision_reason"])
        reject_code = ev.get("reject_reason_code")
        decision_kind = str(ev["decision_kind"])
        visit_eligible = bool(ev["visit_eligible"])
        notification_eligible = bool(ev["notification_eligible"])
        needs_review = bool(ev["classifier_needs_review"]) or bool(clf_needs)
        birder_unknown = str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird")
        from visit_contract import is_named_product_species

        named = is_named_product_species(ev["out_species"], birder_unknown_label=birder_unknown)
        # Entropy/margin OR-flag must downgrade silent accepted_species.
        if accepted and needs_review and named and decision_kind == "accepted_species":
            decision_kind = "review_only_uncertain_species"
            visit_eligible = False
            notification_eligible = False
            if decision_reason == "accepted_species":
                decision_reason = "accepted_binary_track_classifier_uncertain"

        row = apply_runtime_contract(
            {
                "track_id": track_id,
                "accepted": accepted,
                "outcome_bucket": decision_maker._outcome_bucket(
                    accepted=accepted,
                    visit_eligible=visit_eligible,
                    decision_kind=decision_kind,
                ),
                "visit_eligible": visit_eligible,
                "notification_eligible": notification_eligible,
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
                "classifier_needs_review": needs_review,
                "decision_kind": decision_kind,
                "reject_reason_code": reject_code,
                "evidence_state": str(ev["evidence_state"]),
                    "trust_band": decision_maker._trust_band_for_decision(
                        accepted, decision_reason, float(ev["out_conf"]), reject_code
                    ),
                    "pipeline_stage": str(ev.get("pipeline_stage") or STAGE_DETECT_TRACK),
                    "classify_skip_reason": ev.get("classify_skip_reason")
                    or track.get("classify_skip_reason"),
                }
            )
        decisions.append(stamp_recognition_outcome(row, birder_unknown_label=birder_unknown))

    decisions.sort(
        key=lambda item: (
            int(not item.get("accepted", False)),
            -float(item.get("confidence") or 0.0),
            track_id_sort_key(item.get("track_id")),
        )
    )
    return decisions
