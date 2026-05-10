"""Shared fusion layer for live runtime and track regeneration."""

from __future__ import annotations

import logging
from typing import Any, Iterable
from datetime import datetime, timezone

from decision_outcome import compute_outcome_bucket
from multi_camera_confidence import apply_multi_camera_confidence_boost
from birdnet_merge_key import birdnet_merge_key, sqlite_path_for_birdnet_merge
from species_normalizer import merge_detections, normalize
from fusion_model import FusionScorer
from hypothesis_arbitration import apply_hypothesis_arbitration
from runtime_contract import apply_runtime_contract_rows

logger = logging.getLogger(__name__)


def _species_mapping(app_config) -> dict:
    return app_config.get("detection.species_mapping") or {}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_human_like_frigate_event(ev: dict) -> bool:
    labels = {
        str(ev.get("species") or "").strip().lower(),
        str(ev.get("label") or "").strip().lower(),
        str(ev.get("sub_label") or "").strip().lower(),
    }
    labels.discard("")
    return "person" in labels or "human" in labels


def _aggregate_birdnet_scores(
    mqtt_events: Iterable[dict],
    *,
    end_time,
    species_mapping: dict,
    half_life_hours: float = 6.0,
    merge_db_path: str | None = None,
) -> dict[str, dict]:
    scores: dict[str, dict] = {}
    end_dt = end_time
    if getattr(end_dt, "tzinfo", None) is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    half_life_hours = max(0.1, float(half_life_hours or 6.0))
    db_path = merge_db_path if merge_db_path is not None else sqlite_path_for_birdnet_merge()
    for ev in mqtt_events or []:
        if str((ev or {}).get("source") or "").strip().lower() != "birdnet":
            continue
        species = birdnet_merge_key(ev, species_mapping, db_path)
        if not species or species.lower() == "unknown":
            continue
        conf = max(0.0, min(1.0, _safe_float(ev.get("confidence"), 0.0)))
        ts = ev.get("timestamp")
        age_hours = 0.0
        bucket = scores.setdefault(
            species,
            {
                "score": 0.0,
                "support_count": 0,
                "max_confidence": 0.0,
                "timestamp_parse_failed": False,
            },
        )
        if ts:
            try:
                parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age_hours = max(0.0, (end_dt - parsed).total_seconds() / 3600.0)
            except (TypeError, ValueError, OSError):
                age_hours = 0.0
                bucket["timestamp_parse_failed"] = True
        weighted = conf * (0.5 ** (age_hours / half_life_hours))
        bucket["score"] += weighted
        bucket["support_count"] += 1
        bucket["max_confidence"] = max(bucket["max_confidence"], conf)
    return scores


def _attach_audio_evidence(
    detections: list[dict],
    mqtt_events: Iterable[dict],
    *,
    end_time,
    app_config,
) -> list[dict]:
    species_mapping = _species_mapping(app_config)
    birdnet_scores = _aggregate_birdnet_scores(
        mqtt_events,
        end_time=end_time,
        species_mapping=species_mapping,
        half_life_hours=_safe_float(
            app_config.get("processor.birdnet_mqtt_half_life_hours") or 6.0,
            6.0,
        ),
    )
    if not birdnet_scores:
        for d in detections:
            d["_birdnet_prior"] = 0.0
            d["audio_evidence"] = "none"
        return detections

    top_species, top_bucket = max(
        birdnet_scores.items(),
        key=lambda item: (
            _safe_float(item[1].get("score"), 0.0),
            int(item[1].get("support_count") or 0),
        ),
    )
    top_score = _safe_float(top_bucket.get("score"), 0.0)
    top_support_count = int(top_bucket.get("support_count") or 0)
    for d in detections:
        species_name = normalize(
            str(d.get("species_name") or d.get("species") or ""),
            species_mapping,
        )
        support = birdnet_scores.get(species_name)
        prior = _safe_float((support or {}).get("score"), 0.0)
        d["_birdnet_prior"] = prior
        d["audio_top_species"] = top_species
        d["audio_top_score"] = top_score
        d["audio_top_support_count"] = top_support_count
        d["_birdnet_timestamp_parse_failed"] = bool((support or top_bucket or {}).get("timestamp_parse_failed"))
        if support:
            d["audio_evidence"] = "support"
            d["audio_support_count"] = int(support.get("support_count") or 0)
            d["audio_support_species"] = species_name
            continue
        if top_score >= 0.35 and top_species != species_name:
            d["audio_evidence"] = "conflict"
            d["audio_conflict_species"] = top_species
            d["audio_conflict_score"] = top_score
        else:
            d["audio_evidence"] = "none"
    return detections


def _frigate_standalone_prepared_rows(
    frigate_events: Iterable[dict],
    *,
    start_time,
    end_time,
    app_config,
) -> list[dict]:
    """When YOLO/ByteTrack produced no passing tracks, synthesize rows from Frigate MQTT.

    Frigate already triggered recording (and often sees objects YOLO misses at night / distance).
    Without this path, ``merge_detections`` never inserts Frigate-only rows — the clip is dropped
    as zero detections despite MQTT events (see ``recording_finalize`` warning).
    """
    events = [e for e in (frigate_events or []) if e]
    if not events:
        return []

    def _min_and_fallback(suppressed: bool) -> tuple[float, float]:
        if suppressed:
            mn = _safe_float(
                app_config.get("detection.frigate_standalone_excluded_min_score"),
                0.0,
            )
            fb = _safe_float(
                app_config.get("detection.frigate_standalone_excluded_missing_score_fallback"),
                0.58,
            )
        else:
            mn = _safe_float(
                app_config.get("detection.frigate_standalone_min_score"),
                0.40,
            )
            fb = _safe_float(
                app_config.get("detection.frigate_standalone_missing_score_fallback"),
                0.68,
            )
        return max(0.0, min(1.0, mn)), max(0.0, min(1.0, fb))

    species_mapping = _species_mapping(app_config)
    try:
        video_duration = (end_time - start_time).total_seconds() if end_time and start_time else 0.0
    except (TypeError, AttributeError):
        logger.debug("frigate standalone: video_duration from start/end failed", exc_info=True)
        video_duration = 0.0
    video_duration = max(0.0, float(video_duration))

    best: dict[str, dict] = {}
    for ev in events:
        if str((ev or {}).get("source") or "").strip().lower() != "frigate":
            continue
        if _is_human_like_frigate_event(ev):
            continue
        raw = ev.get("species") or ev.get("sub_label") or ev.get("label") or ""
        species = normalize(str(raw), species_mapping)
        if not species or species.lower() == "unknown":
            continue
        suppressed = bool(ev.get("_frigate_merge_suppressed"))
        min_score, miss_fb = _min_and_fallback(suppressed)
        conf = max(0.0, min(1.0, _safe_float(ev.get("confidence"), 0.0)))
        if conf <= 0.0 and miss_fb > 0.0:
            conf = min(1.0, miss_fb)
        if conf < min_score:
            continue
        prev = best.get(species)
        if prev is None or conf > float(prev.get("_raw_conf") or 0.0):
            best[species] = {
                **ev,
                "_raw_conf": conf,
                "_norm_species": species,
                "_standalone_suppressed": suppressed,
            }

    if not best:
        return []

    min_store = _safe_float(
        app_config.get("detection.min_confidence_to_store"),
        0.36,
    )
    notify_standalone = bool(app_config.get("detection.frigate_standalone_notify", True))
    rows: list[dict] = []
    sorted_items = sorted(
        best.items(),
        key=lambda kv: -float(kv[1].get("_raw_conf") or 0.0),
    )
    for i, (_species_name, pack) in enumerate(sorted_items):
        raw_c = float(pack.get("_raw_conf") or 0.0)
        species = str(pack.get("_norm_species") or "")
        conf = max(min_store, min(0.92, raw_c))
        suppressed = bool(pack.get("_standalone_suppressed"))
        kind = "frigate_standalone_excluded" if suppressed else "frigate_standalone"
        reason = "frigate_standalone_excluded_label" if suppressed else "frigate_standalone"
        bbox_norm = pack.get("frigate_bbox_norm")
        frames = None
        if (
            isinstance(bbox_norm, (list, tuple))
            and len(bbox_norm) >= 4
            and all(isinstance(x, (int, float)) for x in bbox_norm[:4])
        ):
            t_mid = video_duration * 0.5 if video_duration > 0 else 0.0
            frames = [{"t": float(t_mid), "bbox": [float(x) for x in bbox_norm[:4]]}]
        row = {
            "track_id": -(i + 1),
            "accepted": True,
            "visit_eligible": True,
            "species_name": species,
            "species": species,
            "confidence": conf,
            "start_time": 0.0,
            "end_time": video_duration,
            "detection_provider": "frigate",
            "detector_confidence": raw_c,
            "classifier_confidence": None,
            "decision_reason": reason,
            "decision_kind": kind,
            "outcome_bucket": compute_outcome_bucket(
                accepted=True,
                visit_eligible=True,
                decision_kind=kind,
            ),
            "notification_eligible": (not suppressed) and notify_standalone,
            "source": "video",
            "frigate_standalone": True,
            "frigate_merge_suppressed": suppressed,
        }
        if frames:
            row["frames"] = frames
        rows.append(row)
    return rows


def _prepared_is_single_generic_bird_track(prepared: list[dict]) -> bool:
    """Single accepted_generic row for species Bird — typical useless YOLO fallback."""
    if len(prepared) != 1:
        return False
    row = prepared[0]
    if str(row.get("decision_kind") or "").strip().lower() != "accepted_generic":
        return False
    name = str(row.get("species_name") or row.get("species") or "").strip().lower()
    return name == "bird"


def prepare_track_results_for_fusion(
    track_results: Iterable[dict],
    app_config,
) -> list[dict]:
    """Normalize DecisionMaker/regen rows into the common video detection shape."""
    species_mapping = _species_mapping(app_config)
    rows: list[dict] = []
    for detection in track_results or []:
        raw_name = detection.get("species_name") or detection.get("species") or detection.get("name") or "unknown"
        normalized_name = normalize(raw_name, species_mapping)
        row = {
            **detection,
            "species_name": normalized_name,
            "species": normalized_name,
            "source": "video",
            "detection_provider": (detection.get("detection_provider") or "yolo"),
        }
        try:
            row["_pre_fusion_confidence"] = float(row.get("confidence") or 0.0)
        except (TypeError, ValueError):
            row["_pre_fusion_confidence"] = 0.0
        rows.append(row)
    return rows


def _frigate_events_camera_scoped(
    frigate_events: Iterable[dict],
    app_config,
) -> list:
    """Оставить только события Frigate с камер из scope Hub (video.cameras + фильтр YAML).

    Если в конфиге нет ни одной валидной камеры — фильтр не применяем (как раньше),
    чтобы юнит-тесты и минимальные конфиги не ломались.
    """
    try:
        from app_config.cameras import cameras_for_processor, get_valid_cameras
        from frigate_scope import frigate_camera_allow_ids
    except ImportError:
        return [e for e in (frigate_events or []) if e]
    valid = get_valid_cameras(app_config.get("video.cameras") or [])
    proc_cams = cameras_for_processor(valid)
    allow = frigate_camera_allow_ids(proc_cams, app_config)
    allow_l = {str(x).strip().lower() for x in allow if str(x).strip()}
    if not allow_l:
        return [e for e in (frigate_events or []) if e]
    out = []
    for e in frigate_events or []:
        if not e:
            continue
        cam = str((e or {}).get("camera") or "").strip().lower()
        if cam in allow_l:
            out.append(e)
        else:
            logger.debug(
                "Fusion: skip Frigate event camera=%s (allowed=%s)",
                cam,
                sorted(allow_l),
            )
    return out


def _clamp_fusion_confidence_inflation(detections: list[dict], app_config: Any) -> list[dict]:
    """Prevent Frigate/BirdNET/learned fusion from rescuing weak non-species tracks.

    По умолчанию итоговый confidence не поднимается выше pre-fusion. Необязательный
    ``detection.fusion_non_species_confidence_slack`` разрешает небольшой «хвост»
    для cross_source_bonus (до base + slack).
    """
    try:
        slack = float((app_config or {}).get("detection.fusion_non_species_confidence_slack") or 0.0)
    except (TypeError, ValueError):
        slack = 0.0
    slack = max(0.0, min(0.25, slack))
    for d in detections:
        kind = str(d.get("decision_kind") or "").strip().lower()
        if kind == "accepted_species":
            continue
        try:
            base = float(d.get("_pre_fusion_confidence") or 0.0)
            cur = float(d.get("confidence") or 0.0)
        except (TypeError, ValueError):
            continue
        cap = base + slack
        if cur > cap:
            d["confidence"] = float(cap)
            d["_fusion_clamped"] = True
    return detections


def build_fused_video_detections(
    video_detections: Iterable[dict],
    mqtt_events: Iterable[dict],
    *,
    start_time,
    end_time,
    app_config,
    fusion_min_confidence_to_store: float | None = None,
) -> list[dict]:
    """Apply shared production fusion rules to video detections.

    BirdNET is excluded from label creation here; its role is confidence
    biasing before DecisionMaker runs. Frigate usually only promotes/boosts
    existing YOLO rows; ``detection.frigate_standalone_when_no_yolo`` adds Frigate-only
    rows when video tracks are empty (see ``_frigate_standalone_prepared_rows``).
    When ``detection.frigate_standalone_when_no_accepted_species`` is true (default),
    synthetic rows are also used when YOLO produced exactly one accepted_generic
    ``Bird`` row (useless fallback) — merge otherwise keeps Bird and drops Frigate's species.
    Frigate events with ``_frigate_merge_suppressed`` (excluded labels) still feed
    standalone but are kept out of ``merge_detections`` so they do not overwrite YOLO species.
    """
    prepared = prepare_track_results_for_fusion(video_detections, app_config)
    merge_window = app_config.get("detection.merge_window_seconds", 5)
    dedup_window = app_config.get("detection.dedup_window_seconds", 45)
    one_per_species = app_config.get("detection.one_per_species", True)
    source_priority = app_config.get("detection.source_priority") or [
        "yolo",
        "frigate",
    ]
    cross_bonus = float(app_config.get("detection.cross_source_confidence_bonus") or 0)
    frigate_events = [
        ev for ev in (mqtt_events or []) if str((ev or {}).get("source") or "").strip().lower() == "frigate"
    ]
    frigate_events = _frigate_events_camera_scoped(frigate_events, app_config)
    frigate_events_for_merge = [ev for ev in frigate_events if not ev.get("_frigate_merge_suppressed")]
    standalone_on = bool(app_config.get("detection.frigate_standalone_when_no_yolo", True))
    standalone_no_species = bool(app_config.get("detection.frigate_standalone_when_no_accepted_species", True))
    want_standalone = (
        standalone_on
        and bool(frigate_events)
        and (
            not prepared
            or (standalone_no_species and len(prepared) == 1 and _prepared_is_single_generic_bird_track(prepared))
        )
    )
    if want_standalone:
        prepared_before = len(prepared)
        synthetic = _frigate_standalone_prepared_rows(
            frigate_events,
            start_time=start_time,
            end_time=end_time,
            app_config=app_config,
        )
        if synthetic:
            extra = prepare_track_results_for_fusion(synthetic, app_config)
            if not prepared:
                prepared = extra
            else:
                # Keep YOLO evidence and add Frigate synthetic candidates; downstream
                # arbitration/conflict rules decide final winner.
                prepared.extend(extra)
            logger.info(
                "Fusion: Frigate standalone — %s synthetic row(s); "
                "yolo_prepared_rows_before=%s (merge uses %s non-suppressed Frigate events)",
                len(synthetic),
                prepared_before,
                len(frigate_events_for_merge),
            )
    fused = merge_detections(
        prepared,
        frigate_events_for_merge,
        start_time,
        end_time,
        merge_window,
        dedup_window,
        one_per_species=one_per_species,
        source_priority=source_priority,
        cross_source_confidence_bonus=cross_bonus,
        species_mapping=_species_mapping(app_config),
        absorb_generic_bird=bool(app_config.get("detection.absorb_generic_bird", True)),
        absorb_generic_bird_overlap_min_sec=float(
            app_config.get("detection.absorb_generic_bird_overlap_min_sec") or 0.1
        ),
        absorb_generic_bird_min_classifier_confidence=float(
            app_config.get("detection.absorb_generic_bird_min_classifier_confidence") or 0.22
        ),
        preserve_equal_rank_conflicts_for_arbitration=True,
    )
    fused = apply_multi_camera_confidence_boost(
        fused,
        frigate_events_for_merge,
        app_config,
    )
    fused = _attach_audio_evidence(
        fused,
        mqtt_events,
        end_time=end_time,
        app_config=app_config,
    )
    fused = apply_hypothesis_arbitration(fused)
    # Optional learned fusion/calibration step. If enabled, the learned scorer
    # produces a calibrated probability from multimodal features and is blended
    # with the existing rule-based confidence.
    try:
        use_learned = bool(app_config.get("detection.use_learned_fusion") or False)
    except (TypeError, ValueError):
        use_learned = False
    if use_learned:
        alpha = float(app_config.get("detection.fusion_alpha") or 0.6)
        model_path = app_config.get("detection.fusion_model_path") or None
        scorer = FusionScorer(model_path=model_path)
        for d in fused:
            # Build a small feature vector from available fields.
            features = {
                "detector_conf": (d.get("detector_confidence") or d.get("detector_conf") or d.get("confidence") or 0.0),
                "classifier_conf": (
                    d.get("classifier_confidence") or d.get("classifier_conf") or d.get("confidence") or 0.0
                ),
                "birdnet_prior": float(d.get("_birdnet_prior") or 0.0),
                "key_frame_score": float(d.get("best_frame_score") or 0.0),
                "key_frame_count": int(d.get("key_frame_count") or 0),
                "multi_camera_count": int(d.get("_multi_camera_count") or 0),
            }
            d["_fusion_model_path"] = model_path
            try:
                fused_score = float(scorer.score(features) or 0.0)
                d["_fusion_scorer_status"] = "ok"
            except Exception:
                logger.debug(
                    "learned FusionScorer.score failed (features_keys=%s)",
                    sorted(features.keys()),
                    exc_info=True,
                )
                fused_score = 0.0
                d["_fusion_scorer_status"] = "error"
            # blend learned score with existing confidence to be conservative by default
            base_conf = float(d.get("confidence") or 0.0)
            final_conf = alpha * fused_score + (1 - alpha) * base_conf
            d["confidence"] = float(final_conf)
            prev_fusion_used = str(d.get("_fusion_used") or "").strip()
            d["_fusion_used"] = f"learned+{prev_fusion_used}" if prev_fusion_used else "learned"
            d["_fusion_score"] = fused_score
    fused = _clamp_fusion_confidence_inflation(fused, app_config)
    fused = apply_runtime_contract_rows(fused)
    if fusion_min_confidence_to_store is not None:
        try:
            min_conf_store = float(fusion_min_confidence_to_store)
        except (TypeError, ValueError):
            min_conf_store = float(app_config.get("detection.min_confidence_to_store") or 0.05)
    else:
        min_conf_store = float(app_config.get("detection.min_confidence_to_store") or 0.05)
    out = [d for d in fused if float(d.get("confidence") or 0.0) >= min_conf_store]
    if len(out) < len(fused):
        logger.info(
            "Fusion: dropped %s row(s) below min_confidence_to_store=%s",
            len(fused) - len(out),
            min_conf_store,
        )
    return out
