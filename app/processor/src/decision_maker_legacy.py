"""Quarantined legacy DecisionMaker cascade (not on hot path).

Production always uses ``linear_pipeline.build_linear_decisions``.
"""
from __future__ import annotations

def get_decisions_legacy(decision_maker, tracks):
    """Legacy cascade — quarantined; not wired into DecisionMaker.get_decisions."""
    import logging

    from app_config.app_config import app_config
    from app_config.visit_eligibility import visit_eligible_for_named_species
    from decision_maker import (
        _classifier_needs_review_flag,
        _is_rodent_detector_label,
        _parse_optional_threshold,
    )
    from persist_mode import defer_static_pinned_reject
    from runtime_contract import apply_runtime_contract, track_id_sort_key
    from track_geometry import static_pinned_track_reason

    logger = logging.getLogger(__name__)

    decisions = []
    store_floor = float(decision_maker.min_confidence_to_store)
    entropy_ge = _parse_optional_threshold(app_config.get("processor.classifier_uncertainty_entropy_ge"))
    margin_le = _parse_optional_threshold(app_config.get("processor.classifier_uncertainty_margin_le"))
    static_cfg = decision_maker._resolve_static_pinned_cfg()
    for track_id, track in tracks.items():
        detector_events = track.get("detector_events") or []
        if not detector_events:
            continue

        static_reason = static_pinned_track_reason(track, static_cfg)
        if static_reason and defer_static_pinned_reject(
            app_config=app_config,
            track=track,
            detector_events=detector_events,
            min_confidence_to_process=float(decision_maker.min_confidence_to_process),
        ):
            static_reason = None
        if static_reason:
            decisions.append(
                apply_runtime_contract(
                    {
                        "track_id": track_id,
                        "accepted": False,
                        "outcome_bucket": "rejected",
                        "decision_reason": "rejected_static_pinned_track",
                        "decision_kind": "rejected",
                        "trust_band": "red",
                        "start_time": track["start_time"],
                        "end_time": track["end_time"],
                        "confidence": 0.0,
                        "detection_provider": "yolo",
                        "reject_reason_code": "insufficient_frames",
                        "reject_detail": static_reason,
                    }
                )
            )
            continue

        dur = track["end_time"] - track["start_time"]
        if dur < decision_maker.min_track_duration:
            logger.debug(
                "Skipping track %s: duration=%.2fs < %ss",
                track_id,
                dur,
                decision_maker.min_track_duration,
            )
            decisions.append(
                apply_runtime_contract(
                    {
                        "track_id": track_id,
                        "accepted": False,
                        "outcome_bucket": "rejected",
                        "decision_reason": "rejected_short_track",
                        "decision_kind": "rejected",
                        "trust_band": "red",
                        "start_time": track["start_time"],
                        "end_time": track["end_time"],
                        "confidence": 0.0,
                        "detection_provider": "yolo",
                        "reject_reason_code": "insufficient_frames",
                    }
                )
            )
            continue

        detector_candidate = decision_maker._pick_detector_candidate(detector_events)
        if detector_candidate is None:
            decisions.append(
                apply_runtime_contract(
                    {
                        "track_id": track_id,
                        "accepted": False,
                        "outcome_bucket": "rejected",
                        "decision_reason": "rejected_missing_detector_candidate",
                        "decision_kind": "rejected",
                        "trust_band": "red",
                        "start_time": track["start_time"],
                        "end_time": track["end_time"],
                        "confidence": 0.0,
                        "detection_provider": "yolo",
                        "reject_reason_code": "insufficient_frames",
                    }
                )
            )
            continue
        detector_label = detector_candidate["label"]
        if _is_rodent_detector_label(detector_label):
            detector_label = "Rodent"
        detector_conf = float(detector_candidate["max_confidence"] or 0.0)

        classifier_events = track.get("classifier_events") or []
        classifier_candidate = decision_maker._pick_classifier_candidate(classifier_events)
        classifier_threshold = None
        accepted = True
        decision_kind = "accepted_species"
        evidence_state = "detector_only"

        visit_eligible = True
        notification_eligible = True
        force_classifier_review = False

        if classifier_candidate is not None:
            species_name = classifier_candidate["species_name"]
            combined = float(classifier_candidate["combined_confidence"] or 0.0)
            threshold = decision_maker._get_threshold_for_species(species_name)
            classifier_threshold = threshold
            if combined >= threshold:
                out_species = species_name
                out_conf = combined
                decision_reason = "accepted_species"
                decision_kind = "accepted_species"
                evidence_state = "species_supported"
            else:
                if not decision_maker.classifier_fallback_bird:
                    logger.debug(
                        "Skipping track %s (%s): classifier confidence=%.3f < %.3f (detector fallback off)",
                        track_id,
                        species_name,
                        combined,
                        threshold,
                    )
                    accepted = False
                    out_species = detector_label
                    out_conf = combined
                    decision_reason = "rejected_classifier_fallback_disabled"
                    decision_kind = "rejected"
                    evidence_state = (
                        "conflicting_classifier_votes"
                        if float(classifier_candidate["vote_share"] or 0.0) <= 0.5
                        else "weak_classifier"
                    )
                elif detector_conf < store_floor:
                    btf = decision_maker._binary_track_first_override(
                        app_config=app_config,
                        track=track,
                        detector_label=detector_label,
                        detector_conf=detector_conf,
                        classifier_candidate=classifier_candidate,
                    )
                    if btf:
                        accepted = bool(btf["accepted"])
                        visit_eligible = bool(btf["visit_eligible"])
                        notification_eligible = bool(btf["notification_eligible"])
                        out_species = btf["out_species"]
                        out_conf = float(btf["out_conf"])
                        decision_reason = btf["decision_reason"]
                        decision_kind = btf["decision_kind"]
                        evidence_state = btf["evidence_state"]
                        force_classifier_review = bool(btf.get("classifier_needs_review"))
                    else:
                        logger.debug(
                            "Skipping track %s: detector confidence=%.3f < min_confidence_to_store=%.3f",
                            track_id,
                            detector_conf,
                            store_floor,
                        )
                        accepted = False
                        out_species = detector_label
                        out_conf = detector_conf
                        decision_reason = "rejected_detector_below_store_floor"
                        decision_kind = "rejected"
                        evidence_state = (
                            "conflicting_classifier_votes"
                            if float(classifier_candidate["vote_share"] or 0.0) <= 0.5
                            else "weak_classifier"
                        )
                else:
                    out_species = detector_label
                    out_conf = min(1.0, max(store_floor, detector_conf))
                    is_rodent = _is_rodent_detector_label(detector_label)
                    is_bird = detector_label.lower() == "bird"
                    if is_rodent:
                        if decision_maker._promotable_generic_rodent(
                            detector_label=detector_label,
                            detector_conf=detector_conf,
                            track=track,
                        ):
                            decision_reason = "fallback_rodent"
                            decision_kind = "accepted_generic"
                            evidence_state = (
                                "conflicting_classifier_votes"
                                if float(classifier_candidate["vote_share"] or 0.0) <= 0.5
                                else "detector_backed_generic"
                            )
                        else:
                            accepted = False
                            out_conf = detector_conf
                            decision_reason = "rejected_weak_generic_rodent"
                            decision_kind = "rejected"
                            evidence_state = "detector_only_low_quality"
                    elif is_bird and not decision_maker._promotable_generic_bird(
                        detector_label=detector_label,
                        detector_conf=detector_conf,
                        track=track,
                    ):
                        btf = decision_maker._binary_track_first_override(
                            app_config=app_config,
                            track=track,
                            detector_label=detector_label,
                            detector_conf=detector_conf,
                            classifier_candidate=classifier_candidate,
                        )
                        if btf:
                            accepted = bool(btf["accepted"])
                            visit_eligible = bool(btf["visit_eligible"])
                            notification_eligible = bool(btf["notification_eligible"])
                            out_species = btf["out_species"]
                            out_conf = float(btf["out_conf"])
                            decision_reason = btf["decision_reason"]
                            decision_kind = btf["decision_kind"]
                            evidence_state = btf["evidence_state"]
                            force_classifier_review = bool(btf.get("classifier_needs_review"))
                        else:
                            accepted = True
                            visit_eligible = True
                            notification_eligible = False
                            decision_reason = "review_only_generic_bird"
                            decision_kind = "review_only_generic"
                            evidence_state = (
                                "conflicting_classifier_votes"
                                if float(classifier_candidate["vote_share"] or 0.0) <= 0.5
                                else "weak_classifier"
                            )
                            force_classifier_review = True
                    else:
                        guess = decision_maker._classifier_best_guess_override(
                            app_config=app_config,
                            track=track,
                            detector_label=detector_label,
                            detector_conf=detector_conf,
                            classifier_candidate=classifier_candidate,
                        )
                        if guess:
                            (
                                accepted,
                                visit_eligible,
                                notification_eligible,
                                out_species,
                                out_conf,
                                decision_reason,
                                decision_kind,
                                evidence_state,
                                force_classifier_review,
                            ) = decision_maker._apply_track_decision_override(guess)
                        elif is_bird:
                            decision_reason = "fallback_bird"
                        elif is_rodent:
                            decision_reason = "fallback_rodent"
                        else:
                            decision_reason = "fallback_detector_generic"
                        if not guess:
                            decision_kind = "accepted_generic"
                            evidence_state = (
                                "conflicting_classifier_votes"
                                if float(classifier_candidate["vote_share"] or 0.0) <= 0.5
                                else "detector_backed_generic"
                            )
        else:
            if detector_conf < store_floor:
                btf = decision_maker._binary_track_first_override(
                    app_config=app_config,
                    track=track,
                    detector_label=detector_label,
                    detector_conf=detector_conf,
                    classifier_candidate=None,
                )
                if btf:
                    accepted = bool(btf["accepted"])
                    visit_eligible = bool(btf["visit_eligible"])
                    notification_eligible = bool(btf["notification_eligible"])
                    out_species = btf["out_species"]
                    out_conf = float(btf["out_conf"])
                    decision_reason = btf["decision_reason"]
                    decision_kind = btf["decision_kind"]
                    evidence_state = btf["evidence_state"]
                    force_classifier_review = bool(btf.get("classifier_needs_review"))
                else:
                    logger.debug(
                        "Skipping track %s (%s): detector confidence=%.3f < min_confidence_to_store=%.3f",
                        track_id,
                        detector_label,
                        detector_conf,
                        store_floor,
                    )
                    accepted = False
                    out_species = detector_label
                    out_conf = detector_conf
                    decision_reason = "rejected_detector_below_store_floor"
                    decision_kind = "rejected"
                    evidence_state = "detector_only_low_confidence"
            else:
                out_species = detector_label
                out_conf = min(1.0, max(store_floor, detector_conf))
                is_rodent = _is_rodent_detector_label(detector_label)
                is_bird = detector_label.lower() == "bird"
                if is_rodent:
                    if decision_maker._promotable_generic_rodent(
                        detector_label=detector_label,
                        detector_conf=detector_conf,
                        track=track,
                    ):
                        decision_reason = "fallback_rodent"
                        decision_kind = "accepted_generic"
                        evidence_state = "detector_only"
                    else:
                        accepted = False
                        out_conf = detector_conf
                        decision_reason = "rejected_weak_generic_rodent"
                        decision_kind = "rejected"
                        evidence_state = "detector_only_low_quality"
                elif is_bird and not decision_maker._promotable_generic_bird(
                    detector_label=detector_label,
                    detector_conf=detector_conf,
                    track=track,
                ):
                    btf = decision_maker._binary_track_first_override(
                        app_config=app_config,
                        track=track,
                        detector_label=detector_label,
                        detector_conf=detector_conf,
                        classifier_candidate=None,
                    )
                    if btf:
                        accepted = bool(btf["accepted"])
                        visit_eligible = bool(btf["visit_eligible"])
                        notification_eligible = bool(btf["notification_eligible"])
                        out_species = btf["out_species"]
                        out_conf = float(btf["out_conf"])
                        decision_reason = btf["decision_reason"]
                        decision_kind = btf["decision_kind"]
                        evidence_state = btf["evidence_state"]
                        force_classifier_review = bool(btf.get("classifier_needs_review"))
                    else:
                        accepted = True
                        visit_eligible = True
                        notification_eligible = False
                        decision_reason = "review_only_generic_bird"
                        decision_kind = "review_only_generic"
                        evidence_state = "detector_only"
                        force_classifier_review = True
                else:
                    if is_bird:
                        decision_reason = "fallback_bird"
                    elif is_rodent:
                        decision_reason = "fallback_rodent"
                    else:
                        decision_reason = "fallback_detector_generic"
                    decision_kind = "accepted_generic"
                    evidence_state = "detector_only"

        reject_reason_code = decision_maker._reject_reason_code(
            decision_reason=decision_reason,
            detector_event_count=detector_candidate["event_count"],
            classifier_event_count=(classifier_candidate["event_count"] if classifier_candidate is not None else 0),
            classifier_vote_share=(classifier_candidate["vote_share"] if classifier_candidate is not None else 0.0),
        )

        clf_entropy = classifier_candidate.get("avg_entropy") if classifier_candidate is not None else None
        clf_margin = classifier_candidate.get("avg_top1_top2_margin") if classifier_candidate is not None else None
        clf_needs_review = _classifier_needs_review_flag(clf_entropy, clf_margin, entropy_ge, margin_le)

        visit_eligible = visit_eligible_for_named_species(
            species_name=out_species,
            visit_eligible=bool(visit_eligible),
            birder_unknown_label=str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird"),
        )
        if not visit_eligible:
            notification_eligible = False

        decisions.append(
            apply_runtime_contract(
                {
                    "track_id": track_id,
                    "accepted": accepted,
                    "outcome_bucket": decision_maker._outcome_bucket(
                        accepted=accepted,
                        visit_eligible=bool(visit_eligible),
                        decision_kind=decision_kind,
                    ),
                    "visit_eligible": bool(visit_eligible),
                    "notification_eligible": bool(notification_eligible),
                    "species_name": out_species,
                    "start_time": track["start_time"],
                    "end_time": track["end_time"],
                    "confidence": out_conf,
                    "best_frame": track.get("best_frame"),
                    "best_frame_score": float(track.get("best_frame_score") or 0.0),
                    "key_frame_count": len(track.get("key_frames") or []),
                    "source": "video",
                    "detection_provider": "yolo",
                    "frames": track.get("frames", []),
                    "decision_reason": decision_reason,
                    "detector_label": detector_label,
                    "detector_confidence": detector_conf,
                    "detector_event_count": detector_candidate["event_count"],
                    "classifier_threshold": classifier_threshold,
                    "classifier_species_name": (
                        classifier_candidate["species_name"] if classifier_candidate is not None else None
                    ),
                    "classifier_confidence": (
                        classifier_candidate["combined_confidence"] if classifier_candidate is not None else None
                    ),
                    "classifier_event_count": (
                        classifier_candidate["event_count"] if classifier_candidate is not None else 0
                    ),
                    "classifier_vote_share": (
                        classifier_candidate["vote_share"] if classifier_candidate is not None else 0.0
                    ),
                    "classifier_entropy": clf_entropy,
                    "classifier_top1_top2_margin": clf_margin,
                    "classifier_needs_review": clf_needs_review or force_classifier_review,
                    "decision_kind": decision_kind,
                    "reject_reason_code": reject_reason_code,
                    "evidence_state": evidence_state,
                    "trust_band": decision_maker._trust_band_for_decision(
                        accepted, decision_reason, out_conf, reject_reason_code
                    ),
                }
            )
        )

    decisions.sort(
        key=lambda item: (
            int(not item.get("accepted", False)),
            -float(item.get("confidence") or 0.0),
            track_id_sort_key(item.get("track_id")),
        )
    )
    return decisions

