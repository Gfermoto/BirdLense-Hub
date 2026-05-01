import logging
import time
from collections import Counter
import re

from decision_outcome import compute_outcome_bucket
from runtime_contract import apply_runtime_contract

logger = logging.getLogger(__name__)

# Default min confidence; can be overridden via app_config processor.min_confidence_to_process.
DEFAULT_MIN_CONFIDENCE = 0.30


def _parse_optional_threshold(raw):
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _classifier_needs_review_flag(entropy, margin, entropy_ge, margin_le):
    """True если энтропия/ margin выходят за пороги из конфига (#370, AL)."""
    if entropy_ge is None and margin_le is None:
        return False
    hi = False
    lo = False
    if entropy_ge is not None and entropy is not None:
        hi = float(entropy) >= float(entropy_ge)
    if margin_le is not None and margin is not None:
        lo = float(margin) <= float(margin_le)
    return bool(hi or lo)


def _is_rodent_detector_label(detector_label: str) -> bool:
    """Канон в пайплайне — ``Rodent``; ``squirrel`` только для старых событий/логов."""
    d = str(detector_label or "").strip().lower()
    return d in {"rodent", "squirrel"}


def _normalized_species_keys(species_name):
    raw = str(species_name or "").strip()
    if not raw:
        return []

    def _normalize_key(value):
        return " ".join(str(value or "").replace("_", " ").replace("-", " ").strip().lower().split())

    keys = []
    raw_key = _normalize_key(raw)
    if raw_key:
        keys.append(raw_key)

    match = re.match(r"^.+?\s*\(([^)]+)\)\s*$", raw)
    if match:
        common_key = _normalize_key(match.group(1))
        if common_key and common_key not in keys:
            keys.append(common_key)

    return keys


class DecisionMaker:
    def __init__(
        self,
        max_record_seconds=60,
        max_inactive_seconds=10,
        min_track_duration=1.0,
        min_confidence_to_process=None,
        species_confidence_overrides=None,
        post_record_seconds=0,
        min_confidence_to_store=0.30,
        classifier_fallback_bird=True,
        generic_bird_min_detector_conf=None,
        generic_bird_min_frames=3,
        generic_bird_min_area_frac=0.01,
        generic_bird_min_best_frame_score=6.5,
        generic_rodent_min_frames=1,
        generic_rodent_max_area_frac=1.0,
        generic_rodent_min_best_frame_score=0.0,
    ):
        self.max_record_seconds = max_record_seconds
        self.max_inactive_seconds = max_inactive_seconds
        try:
            pr = float(post_record_seconds or 0)
        except (TypeError, ValueError):
            pr = 0.0
        # post-roll: extend «no detection» tail after last activity (#157)
        self._effective_max_inactive = float(max_inactive_seconds or 0) + max(0.0, min(pr, 120.0))
        self.min_track_duration = min_track_duration
        self.min_confidence_to_process = (
            min_confidence_to_process if min_confidence_to_process is not None else DEFAULT_MIN_CONFIDENCE
        )
        self.species_confidence_overrides = species_confidence_overrides or {}
        self._species_confidence_override_keys = {
            key: value
            for name, value in self.species_confidence_overrides.items()
            for key in _normalized_species_keys(name)
        }
        try:
            self.min_confidence_to_store = float(min_confidence_to_store)
        except (TypeError, ValueError):
            self.min_confidence_to_store = 0.30
        self.classifier_fallback_bird = bool(classifier_fallback_bird)
        try:
            self.generic_bird_min_detector_conf = (
                float(generic_bird_min_detector_conf)
                if generic_bird_min_detector_conf is not None
                else max(float(self.min_confidence_to_store), 0.45)
            )
        except (TypeError, ValueError):
            self.generic_bird_min_detector_conf = max(float(self.min_confidence_to_store), 0.45)
        try:
            self.generic_bird_min_frames = max(1, int(generic_bird_min_frames))
        except (TypeError, ValueError):
            self.generic_bird_min_frames = 3
        try:
            self.generic_bird_min_area_frac = max(0.0, min(1.0, float(generic_bird_min_area_frac)))
        except (TypeError, ValueError):
            self.generic_bird_min_area_frac = 0.01
        try:
            self.generic_bird_min_best_frame_score = float(generic_bird_min_best_frame_score)
        except (TypeError, ValueError):
            self.generic_bird_min_best_frame_score = 6.5
        try:
            self.generic_rodent_min_frames = max(1, int(generic_rodent_min_frames))
        except (TypeError, ValueError):
            self.generic_rodent_min_frames = 1
        try:
            self.generic_rodent_max_area_frac = max(0.0, min(1.0, float(generic_rodent_max_area_frac)))
        except (TypeError, ValueError):
            self.generic_rodent_max_area_frac = 1.0
        try:
            self.generic_rodent_min_best_frame_score = float(generic_rodent_min_best_frame_score)
        except (TypeError, ValueError):
            self.generic_rodent_min_best_frame_score = 0.0
        self._runtime_override_defaults = {
            "min_track_duration": self.min_track_duration,
            "min_confidence_to_process": self.min_confidence_to_process,
        }
        self.reset()

    def _trust_band_for_decision(
        self,
        accepted: bool,
        reason: str,
        confidence: float,
        reject_reason_code: str | None = None,
    ) -> str:
        if not accepted:
            if reject_reason_code == "conflicting_evidence":
                return "gray"
            return "red"
        if reason == "accepted_species":
            return "green" if float(confidence or 0.0) >= 0.75 else "yellow"
        if reason == "review_only_generic_bird":
            return "yellow"
        return "gray"

    def _reject_reason_code(
        self,
        *,
        decision_reason: str,
        detector_event_count: int,
        classifier_event_count: int,
        classifier_vote_share: float = 0.0,
    ) -> str | None:
        if decision_reason in {
            "rejected_short_track",
            "rejected_missing_detector_candidate",
        }:
            return "insufficient_frames"
        if decision_reason in {
            "rejected_detector_below_store_floor",
            "rejected_classifier_fallback_disabled",
            "rejected_weak_generic_bird",
            "rejected_weak_generic_rodent",
        }:
            if classifier_event_count > 1 and float(classifier_vote_share or 0.0) <= 0.5:
                return "conflicting_evidence"
            if detector_event_count <= 1 or classifier_event_count <= 1:
                return "insufficient_frames"
            return "low_confidence"
        return None

    def _outcome_bucket(
        self,
        *,
        accepted: bool,
        visit_eligible: bool,
        decision_kind: str,
    ) -> str:
        return compute_outcome_bucket(
            accepted=accepted,
            visit_eligible=visit_eligible,
            decision_kind=decision_kind,
        )

    def _bbox_area_frac(self, bbox) -> float:
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return 0.0
        try:
            x1, y1, x2, y2 = [float(b) for b in bbox]
        except (TypeError, ValueError):
            return 0.0
        w = max(0.0, x2 - x1)
        h = max(0.0, y2 - y1)
        return max(0.0, min(1.0, w * h))

    def _generic_bird_visual_support(self, track: dict) -> tuple[float, int]:
        frames = track.get("frames") or []
        best = 0.0
        n = 0
        for fr in frames:
            if not isinstance(fr, dict):
                continue
            area = self._bbox_area_frac(fr.get("bbox"))
            if area > 0:
                n += 1
                best = max(best, area)
        return best, n

    def _promotable_generic_bird(
        self,
        *,
        detector_label: str,
        detector_conf: float,
        track: dict,
    ) -> bool:
        """Generic Bird is accepted for visits/notifications only with stronger visual support."""
        if str(detector_label or "").strip().lower() != "bird":
            return True
        # Configurable defaults: keep obvious generic Bird visits, but avoid tiny/noisy tracks.
        min_det = max(float(self.min_confidence_to_store), float(self.generic_bird_min_detector_conf))
        if float(detector_conf or 0.0) < min_det:
            return False
        max_area, n_frames = self._generic_bird_visual_support(track)
        if n_frames < self.generic_bird_min_frames:
            return False
        if max_area < self.generic_bird_min_area_frac:
            return False
        if float(track.get("best_frame_score") or 0.0) < self.generic_bird_min_best_frame_score:
            return False
        return True

    def _promotable_generic_rodent(
        self,
        *,
        detector_label: str,
        detector_conf: float,
        track: dict,
    ) -> bool:
        if not _is_rodent_detector_label(detector_label):
            return True
        if float(detector_conf or 0.0) < float(self.min_confidence_to_store):
            return False
        max_area, n_frames = self._generic_bird_visual_support(track)
        if n_frames <= 0:
            return True
        if n_frames < self.generic_rodent_min_frames:
            return False
        if max_area > self.generic_rodent_max_area_frac:
            return False
        if float(track.get("best_frame_score") or 0.0) < self.generic_rodent_min_best_frame_score:
            return False
        return True

    def _get_threshold_for_species(self, species_name):
        """Return min confidence threshold for species. Override or default."""
        direct = self.species_confidence_overrides.get(species_name)
        if direct is not None:
            return direct
        for key in _normalized_species_keys(species_name):
            mapped = self._species_confidence_override_keys.get(key)
            if mapped is not None:
                return mapped
        keys = _normalized_species_keys(species_name)
        for key in keys:
            if any(tok in key for tok in ("rodent", "squirrel", "chipmunk", "sciurus")):
                store_floor = float(self.min_confidence_to_store)
                relaxed = float(self.min_confidence_to_process) - 0.10
                return max(store_floor, min(0.32, relaxed))
        return self.min_confidence_to_process

    def reset(self):
        self.stop_recording_decided = False
        self.species_decided = False
        self.start_time = time.time()
        self.inactive_start_time = None
        self.reset_runtime_overrides()

    def apply_runtime_overrides(self, overrides: dict | None):
        overrides = overrides or {}
        if "min_track_duration" in overrides:
            try:
                self.min_track_duration = float(overrides["min_track_duration"])
            except (TypeError, ValueError):
                pass
        if "min_confidence_to_process" in overrides:
            try:
                self.min_confidence_to_process = float(overrides["min_confidence_to_process"])
            except (TypeError, ValueError):
                pass

    def reset_runtime_overrides(self):
        self.min_track_duration = self._runtime_override_defaults["min_track_duration"]
        self.min_confidence_to_process = self._runtime_override_defaults["min_confidence_to_process"]

    def update_has_detections(self, has_detections):
        if not has_detections:
            if self.inactive_start_time is None:
                self.inactive_start_time = time.time()
        else:
            self.inactive_start_time = None

    def decide_stop_recording(self):
        """True once when max duration or inactivity warrants stop; then always False.

        One-shot: first True records the decision; later calls avoid re-triggering
        shutdown on every tick.
        """
        if self.stop_recording_decided:
            return False
        reached_max_record_seconds = (time.time() - self.start_time) >= self.max_record_seconds
        reached_max_inactive_seconds = (
            self.inactive_start_time and (time.time() - self.inactive_start_time) >= self._effective_max_inactive
        )
        decision = reached_max_inactive_seconds or reached_max_record_seconds
        self.stop_recording_decided = decision
        return decision

    def decide_species(self, tracks):
        if self.species_decided:
            return None
        results = self.get_results(tracks)
        if len(results) > 0:
            self.species_decided = True
            return results[0]["species_name"]
        return None

    def get_first_species_result(self, tracks):
        """Return first result dict (species_name, best_frame, ...) or None."""
        if self.species_decided:
            return None
        results = self.get_results(tracks)
        if len(results) > 0:
            self.species_decided = True
            return results[0]
        return None

    def _pick_detector_candidate(self, detector_events):
        labels = [str(ev.get("label") or "").strip() for ev in detector_events if str(ev.get("label") or "").strip()]
        if not labels:
            return None
        counts = Counter(labels)
        max_count = max(counts.values())
        candidates = [label for label, count in counts.items() if count == max_count]

        def _label_score(label):
            relevant = [
                float(ev.get("confidence") or 0.0)
                for ev in detector_events
                if str(ev.get("label") or "").strip() == label
            ]
            max_conf = max(relevant) if relevant else 0.0
            avg_conf = sum(relevant) / len(relevant) if relevant else 0.0
            return (max_conf, avg_conf, label)

        best_label = max(candidates, key=_label_score)
        relevant = [
            float(ev.get("confidence") or 0.0)
            for ev in detector_events
            if str(ev.get("label") or "").strip() == best_label
        ]
        return {
            "label": best_label,
            "count": counts[best_label],
            "event_count": len(detector_events),
            "max_confidence": max(relevant) if relevant else 0.0,
            "avg_confidence": (sum(relevant) / len(relevant)) if relevant else 0.0,
        }

    def _pick_classifier_candidate(self, classifier_events):
        names = [
            str(ev.get("species_name") or "").strip()
            for ev in classifier_events
            if str(ev.get("species_name") or "").strip()
        ]
        if not names:
            return None
        counts = Counter(names)
        max_count = max(counts.values())
        candidates = [name for name, count in counts.items() if count == max_count]

        def _name_score(name):
            relevant = [
                float(ev.get("combined_confidence") or 0.0)
                for ev in classifier_events
                if str(ev.get("species_name") or "").strip() == name
            ]
            max_conf = max(relevant) if relevant else 0.0
            avg_conf = sum(relevant) / len(relevant) if relevant else 0.0
            return (max_conf, avg_conf, name)

        best_name = max(candidates, key=_name_score)
        relevant = [ev for ev in classifier_events if str(ev.get("species_name") or "").strip() == best_name]
        vote_share = counts[best_name] / len(classifier_events)
        avg_classifier_conf = sum(float(ev.get("confidence") or 0.0) for ev in relevant) / len(relevant)
        avg_combined_conf = sum(float(ev.get("combined_confidence") or 0.0) for ev in relevant) / len(relevant)
        ent_vals = [float(ev["entropy"]) for ev in relevant if ev.get("entropy") is not None]
        margin_vals = [float(ev["top1_top2_margin"]) for ev in relevant if ev.get("top1_top2_margin") is not None]
        avg_entropy = sum(ent_vals) / len(ent_vals) if ent_vals else None
        avg_top1_top2_margin = sum(margin_vals) / len(margin_vals) if margin_vals else None
        return {
            "species_name": best_name,
            "vote_share": vote_share,
            "event_count": len(classifier_events),
            "avg_classifier_confidence": avg_classifier_conf,
            "avg_combined_confidence": avg_combined_conf,
            "combined_confidence": vote_share * avg_combined_conf,
            "avg_entropy": avg_entropy,
            "avg_top1_top2_margin": avg_top1_top2_margin,
        }

    def get_decisions(self, tracks):
        from app_config.app_config import app_config

        decisions = []
        store_floor = float(self.min_confidence_to_store)
        entropy_ge = _parse_optional_threshold(app_config.get("processor.classifier_uncertainty_entropy_ge"))
        margin_le = _parse_optional_threshold(app_config.get("processor.classifier_uncertainty_margin_le"))
        for track_id, track in tracks.items():
            detector_events = track.get("detector_events") or []
            if not detector_events:
                continue

            dur = track["end_time"] - track["start_time"]
            if dur < self.min_track_duration:
                logger.debug(
                    "Skipping track %s: duration=%.2fs < %ss",
                    track_id,
                    dur,
                    self.min_track_duration,
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
                        }
                    )
                )
                continue

            detector_candidate = self._pick_detector_candidate(detector_events)
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
                        }
                    )
                )
                continue
            detector_label = detector_candidate["label"]
            if _is_rodent_detector_label(detector_label):
                detector_label = "Rodent"
            detector_conf = float(detector_candidate["max_confidence"] or 0.0)

            classifier_events = track.get("classifier_events") or []
            classifier_candidate = self._pick_classifier_candidate(classifier_events)
            classifier_threshold = None
            accepted = True
            decision_kind = "accepted_species"
            evidence_state = "detector_only"

            visit_eligible = True
            notification_eligible = True

            if classifier_candidate is not None:
                species_name = classifier_candidate["species_name"]
                combined = float(classifier_candidate["combined_confidence"] or 0.0)
                threshold = self._get_threshold_for_species(species_name)
                classifier_threshold = threshold
                if combined >= threshold:
                    out_species = species_name
                    out_conf = combined
                    decision_reason = "accepted_species"
                    decision_kind = "accepted_species"
                    evidence_state = "species_supported"
                else:
                    if not self.classifier_fallback_bird:
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
                            if self._promotable_generic_rodent(
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
                        elif is_bird and not self._promotable_generic_bird(
                            detector_label=detector_label,
                            detector_conf=detector_conf,
                            track=track,
                        ):
                            accepted = True
                            visit_eligible = False
                            notification_eligible = False
                            decision_reason = "review_only_generic_bird"
                            decision_kind = "review_only_generic"
                            evidence_state = (
                                "conflicting_classifier_votes"
                                if float(classifier_candidate["vote_share"] or 0.0) <= 0.5
                                else "weak_classifier"
                            )
                        else:
                            if is_bird:
                                decision_reason = "fallback_bird"
                            elif is_rodent:
                                decision_reason = "fallback_rodent"
                            else:
                                decision_reason = "fallback_detector_generic"
                            decision_kind = "accepted_generic"
                            evidence_state = (
                                "conflicting_classifier_votes"
                                if float(classifier_candidate["vote_share"] or 0.0) <= 0.5
                                else "detector_backed_generic"
                            )
            else:
                if detector_conf < store_floor:
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
                        if self._promotable_generic_rodent(
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
                    elif is_bird and not self._promotable_generic_bird(
                        detector_label=detector_label,
                        detector_conf=detector_conf,
                        track=track,
                    ):
                        accepted = True
                        visit_eligible = False
                        notification_eligible = False
                        decision_reason = "review_only_generic_bird"
                        decision_kind = "review_only_generic"
                        evidence_state = "detector_only"
                    else:
                        if is_bird:
                            decision_reason = "fallback_bird"
                        elif is_rodent:
                            decision_reason = "fallback_rodent"
                        else:
                            decision_reason = "fallback_detector_generic"
                        decision_kind = "accepted_generic"
                        evidence_state = "detector_only"

            reject_reason_code = self._reject_reason_code(
                decision_reason=decision_reason,
                detector_event_count=detector_candidate["event_count"],
                classifier_event_count=(classifier_candidate["event_count"] if classifier_candidate is not None else 0),
                classifier_vote_share=(classifier_candidate["vote_share"] if classifier_candidate is not None else 0.0),
            )

            clf_entropy = classifier_candidate.get("avg_entropy") if classifier_candidate is not None else None
            clf_margin = classifier_candidate.get("avg_top1_top2_margin") if classifier_candidate is not None else None
            clf_needs_review = _classifier_needs_review_flag(clf_entropy, clf_margin, entropy_ge, margin_le)

            decisions.append(
                apply_runtime_contract(
                    {
                        "track_id": track_id,
                        "accepted": accepted,
                        "outcome_bucket": self._outcome_bucket(
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
                        "classifier_needs_review": clf_needs_review,
                        "decision_kind": decision_kind,
                        "reject_reason_code": reject_reason_code,
                        "evidence_state": evidence_state,
                        "trust_band": self._trust_band_for_decision(
                            accepted, decision_reason, out_conf, reject_reason_code
                        ),
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

    def get_results(self, tracks):
        return [item for item in self.get_decisions(tracks) if item.get("accepted", False)]
