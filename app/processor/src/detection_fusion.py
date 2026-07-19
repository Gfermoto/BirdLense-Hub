"""Shared fusion layer for live runtime and track regeneration."""

from __future__ import annotations

import logging
from typing import Any, Iterable
from datetime import datetime, timezone, timedelta
import math

from decision_outcome import compute_outcome_bucket
from multi_camera_confidence import apply_multi_camera_confidence_boost
from birdnet_merge_key import birdnet_merge_key, sqlite_path_for_birdnet_merge
from species_normalizer import merge_detections, normalize
from fusion_model import FusionScorer
from hypothesis_arbitration import apply_hypothesis_arbitration
from runtime_contract import apply_runtime_contract_rows
from weighted_species_arbiter import apply_weighted_species_arbiter
from species_mapping_config import build_species_mapping
from persist_mode import passes_binary_track_first_store_floor
from processor_config_defaults import ABSORB_GENERIC_BIRD_MIN_CLASSIFIER_CONFIDENCE, config_float

logger = logging.getLogger(__name__)


def _species_mapping(app_config) -> dict:
    return build_species_mapping(app_config)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def skip_frigate_ev_for_standalone(ev: dict | None, app_config) -> bool:
    """True when label/species intersect ``detection.frigate_standalone_skip_labels``."""
    if not isinstance(ev, dict) or not ev:
        return False
    raw = app_config.get("detection.frigate_standalone_skip_labels")
    if not isinstance(raw, (list, tuple)):
        return False
    skip = {str(x).strip().lower() for x in raw if str(x).strip()}
    if not skip:
        return False
    labels = {
        str(ev.get("species") or "").strip().lower(),
        str(ev.get("label") or "").strip().lower(),
        str(ev.get("sub_label") or "").strip().lower(),
    }
    labels.discard("")
    return bool(labels & skip)


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
            # Deterministic tie-break for equal score/support.
            str(item[0] or "").strip().lower(),
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
        max_event_age_s = float(app_config.get("detection.frigate_standalone_max_event_age_seconds") or 10.0)
    except (TypeError, ValueError):
        max_event_age_s = 10.0
    max_event_age_s = max(1.0, min(120.0, max_event_age_s))
    require_geometry = bool(app_config.get("detection.frigate_standalone_require_geometry", True))
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
        ts_raw = ev.get("timestamp")
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            # Без валидного времени событие не годится для standalone-спасения.
            continue
        if start_time and ts < (start_time - timedelta(seconds=max_event_age_s)):
            continue
        if end_time and ts > (end_time + timedelta(seconds=2.0)):
            continue
        if skip_frigate_ev_for_standalone(ev, app_config):
            continue
        has_geometry_raw = ev.get("_frigate_has_geometry")
        # Backward compatibility: synthetic/tests may not carry the flag yet.
        has_geometry = True if has_geometry_raw is None else bool(has_geometry_raw)
        if not has_geometry and isinstance(ev.get("frigate_bbox_norm"), (list, tuple)):
            has_geometry = len(ev.get("frigate_bbox_norm") or []) >= 4
        if (
            require_geometry
            and not has_geometry
            and not bool(ev.get("_synthetic_trigger_fallback"))
            and not bool(ev.get("_session_trigger_snapshot"))
        ):
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
            "source_reason": "blind_yolo",
            "confidence_level": "low",
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
        bbox = pack.get("frigate_bbox_norm")
        preserve_bbox = bool(app_config.get("detection.frigate_standalone_preserve_bbox_frames", False))
        if preserve_bbox and isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            try:
                rel_t = max(
                    0.0,
                    min(
                        video_duration,
                        (datetime.fromisoformat(str(pack.get("timestamp")).replace("Z", "+00:00")) - start_time).total_seconds(),
                    ),
                )
                row["frames"] = [{"t": round(rel_t, 3), "bbox": [float(x) for x in bbox[:4]]}]
            except (TypeError, ValueError, AttributeError):
                logger.debug("frigate standalone bbox frame build failed", exc_info=True)
        aliases: list[str] = []
        for key in ("species", "sub_label", "label"):
            raw_name = str((pack or {}).get(key) or "").strip()
            if raw_name and raw_name.lower() not in {"bird", "unknown"} and raw_name not in aliases:
                aliases.append(raw_name)
        if aliases:
            row["source_aliases"] = aliases
        scientific_name = str((pack or {}).get("scientific_name") or "").strip()
        if scientific_name:
            row["source_scientific_names"] = [scientific_name]
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


def _prepared_has_accepted_species(prepared: list[dict]) -> bool:
    """True when at least one prepared row is an accepted species result."""
    for row in prepared or []:
        kind = str(row.get("decision_kind") or "").strip().lower()
        if kind == "accepted_species" and bool(row.get("accepted", True)):
            return True
    return False


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
        source_aliases: list[str] = []
        raw_clean = str(raw_name or "").strip()
        if raw_clean and raw_clean != normalized_name:
            source_aliases.append(raw_clean)
        row = {
            **detection,
            "species_name": normalized_name,
            "species": normalized_name,
            "source": "video",
            "detection_provider": (detection.get("detection_provider") or "yolo"),
        }
        if source_aliases:
            row["source_aliases"] = source_aliases
        try:
            row["_pre_fusion_confidence"] = float(row.get("confidence") or 0.0)
        except (TypeError, ValueError):
            row["_pre_fusion_confidence"] = 0.0
        rows.append(row)
    return rows


def _frigate_events_camera_scoped(
    frigate_events: Iterable[dict],
    app_config,
    *,
    triggered_camera: str | None = None,
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
    valid = get_valid_cameras(video_config=(app_config.get("video") or {}))
    proc_cams = cameras_for_processor(valid)
    allow = frigate_camera_allow_ids(proc_cams, app_config)
    allow_l = {str(x).strip().lower() for x in allow if str(x).strip()}
    trig = str(triggered_camera or "").strip().lower()
    if trig:
        allow_l = {trig} if not allow_l else {trig} & allow_l
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


def _bbox_iou_norm(a: list[float], b: list[float]) -> float:
    try:
        ax1, ay1, ax2, ay2 = [float(x) for x in a]
        bx1, by1, bx2, by2 = [float(x) for x in b]
    except (TypeError, ValueError):
        return 0.0
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    aa = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    ba = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    den = aa + ba - inter
    if den <= 1e-9:
        return 0.0
    return max(0.0, min(1.0, inter / den))


def _bbox_center_dist_norm(a: list[float], b: list[float]) -> float:
    try:
        ax1, ay1, ax2, ay2 = [float(x) for x in a]
        bx1, by1, bx2, by2 = [float(x) for x in b]
    except (TypeError, ValueError):
        return 1.0
    acx, acy = (ax1 + ax2) * 0.5, (ay1 + ay2) * 0.5
    bcx, bcy = (bx1 + bx2) * 0.5, (by1 + by2) * 0.5
    return math.sqrt((acx - bcx) ** 2 + (acy - bcy) ** 2)


def _row_bbox_first_last(row: dict) -> tuple[list[float] | None, list[float] | None]:
    frames = row.get("frames")
    if not isinstance(frames, list) or not frames:
        return None, None
    first = frames[0] if isinstance(frames[0], dict) else None
    last = frames[-1] if isinstance(frames[-1], dict) else None
    return (
        (first.get("bbox") if first else None),
        (last.get("bbox") if last else None),
    )


def _frame_time_key(frame: dict) -> float | None:
    try:
        return round(float(frame.get("t") or 0.0), 2)
    except (TypeError, ValueError):
        return None


def _max_same_timestamp_iou(a_frames: list[dict], b_frames: list[dict]) -> float:
    by_t: dict[float, list[float]] = {}
    for fr in a_frames:
        if not isinstance(fr, dict):
            continue
        key = _frame_time_key(fr)
        bbox = fr.get("bbox")
        if key is not None and bbox is not None:
            by_t[key] = bbox
    best = 0.0
    for fr in b_frames:
        if not isinstance(fr, dict):
            continue
        key = _frame_time_key(fr)
        bbox = fr.get("bbox")
        if key is None or bbox is None or key not in by_t:
            continue
        best = max(best, _bbox_iou_norm(by_t[key], bbox))
    return best


def _merged_track_frames(prev: dict, row: dict) -> list[dict]:
    prev_frames = prev.get("frames") if isinstance(prev.get("frames"), list) else []
    row_frames = row.get("frames") if isinstance(row.get("frames"), list) else []
    if not prev_frames and not row_frames:
        return []
    prev_conf = float(prev.get("confidence") or 0.0)
    row_conf = float(row.get("confidence") or 0.0)
    by_t: dict[float, tuple[float, int, dict]] = {}
    order = 0
    for conf, frames in ((prev_conf, prev_frames), (row_conf, row_frames)):
        for fr in frames:
            if not isinstance(fr, dict):
                continue
            key = _frame_time_key(fr)
            if key is None:
                continue
            current = by_t.get(key)
            if current is None or conf >= current[0]:
                by_t[key] = (conf, order, fr)
            order += 1
    return [item[2] for _key, item in sorted(by_t.items(), key=lambda kv: (kv[0], kv[1][1]))]


def _merge_adjacent_yolo_fragments(detections: list[dict], app_config: Any) -> list[dict]:
    """Merge same-species adjacent YOLO fragments (short gap + spatial continuity)."""
    if not detections:
        return detections
    try:
        enabled = bool((app_config or {}).get("detection.track_fragment_merge_enabled", True))
    except Exception:
        enabled = True
    if not enabled:
        return detections
    try:
        max_gap = float((app_config or {}).get("detection.track_fragment_merge_gap_sec") or 1.2)
    except (TypeError, ValueError):
        max_gap = 1.2
    try:
        min_iou = float((app_config or {}).get("detection.track_fragment_merge_min_iou") or 0.08)
    except (TypeError, ValueError):
        min_iou = 0.08
    try:
        max_center = float((app_config or {}).get("detection.track_fragment_merge_max_center_dist") or 0.18)
    except (TypeError, ValueError):
        max_center = 0.18
    try:
        overlap_min_iou = float(
            (app_config or {}).get("detection.track_fragment_overlap_merge_min_iou") or 0.45
        )
    except (TypeError, ValueError):
        overlap_min_iou = 0.45
    max_gap = max(0.0, min(5.0, max_gap))
    min_iou = max(0.0, min(1.0, min_iou))
    max_center = max(0.0, min(1.0, max_center))
    overlap_min_iou = max(0.0, min(1.0, overlap_min_iou))

    rows = sorted(detections, key=lambda r: float(r.get("start_time") or 0.0))
    out: list[dict] = []
    merged_count = 0
    for row in rows:
        if not out:
            out.append(row)
            continue
        prev = out[-1]
        if str(prev.get("detection_provider") or "").strip().lower() != "yolo":
            out.append(row)
            continue
        if str(row.get("detection_provider") or "").strip().lower() != "yolo":
            out.append(row)
            continue
        if str(prev.get("species_name") or "") != str(row.get("species_name") or ""):
            out.append(row)
            continue
        prev_end = float(prev.get("end_time") or 0.0)
        cur_start = float(row.get("start_time") or 0.0)
        gap = cur_start - prev_end
        _, prev_last = _row_bbox_first_last(prev)
        row_first, _ = _row_bbox_first_last(row)
        prev_frames = prev.get("frames") if isinstance(prev.get("frames"), list) else []
        row_frames = row.get("frames") if isinstance(row.get("frames"), list) else []
        if gap < 0.0:
            if _max_same_timestamp_iou(prev_frames, row_frames) < overlap_min_iou:
                out.append(row)
                continue
        elif gap > max_gap:
            out.append(row)
            continue
        elif prev_last is None or row_first is None:
            out.append(row)
            continue
        else:
            iou = _bbox_iou_norm(prev_last, row_first)
            cdist = _bbox_center_dist_norm(prev_last, row_first)
            if iou < min_iou and cdist > max_center:
                out.append(row)
                continue
        merged = {**prev}
        merged["end_time"] = max(float(prev.get("end_time") or 0.0), float(row.get("end_time") or 0.0))
        merged["confidence"] = max(float(prev.get("confidence") or 0.0), float(row.get("confidence") or 0.0))
        merged["detector_confidence"] = max(
            float(prev.get("detector_confidence") or 0.0),
            float(row.get("detector_confidence") or 0.0),
        )
        merged_frames = _merged_track_frames(prev, row)
        if merged_frames:
            merged["frames"] = merged_frames
        merged["track_fragment_merged"] = True
        merged["merged_track_ids"] = sorted(
            {
                int(x)
                for x in [
                    prev.get("track_id"),
                    row.get("track_id"),
                    *(prev.get("merged_track_ids") or []),
                    *(row.get("merged_track_ids") or []),
                ]
                if isinstance(x, int)
            }
        )
        out[-1] = merged
        merged_count += 1
    if merged_count:
        logger.info("Fusion: merged %s adjacent YOLO track fragment(s)", merged_count)
    return out


def build_fused_video_detections(
    video_detections: Iterable[dict],
    mqtt_events: Iterable[dict],
    *,
    start_time,
    end_time,
    app_config,
    fusion_min_confidence_to_store: float | None = None,
    triggered_camera: str | None = None,
    yolo_blind_confirmed: bool = False,
    yolo_blind_score: float = 0.0,
) -> list[dict]:
    """Apply shared production fusion rules to video detections.

    BirdNET is excluded from label creation here; its role is confidence
    biasing before DecisionMaker runs. Frigate usually only promotes/boosts
    existing YOLO rows; ``detection.frigate_standalone_when_no_yolo`` adds Frigate-only
    rows when video tracks are empty (see ``_frigate_standalone_prepared_rows``).
    When ``detection.frigate_standalone_when_no_accepted_species`` is true,
    synthetic rows are also used when YOLO produced no accepted species result
    (including the classic single accepted_generic ``Bird`` fallback).
    Frigate events with ``_frigate_merge_suppressed`` (excluded labels) still feed
    standalone but are kept out of ``merge_detections`` so they do not overwrite YOLO species.
    """
    prepared = prepare_track_results_for_fusion(video_detections, app_config)
    merge_window = app_config.get("detection.merge_window_seconds", 5)
    dedup_window = app_config.get("detection.dedup_window_seconds", 45)
    one_per_species = app_config.get("detection.one_per_species", True)
    one_per_species_keep_distinct_tracks = bool(app_config.get("detection.one_per_species_keep_distinct_tracks", False))
    source_priority_cfg = app_config.get("detection.source_priority") or [
        "yolo",
        "frigate",
    ]
    source_priority = [str(x).strip().lower() for x in source_priority_cfg if str(x).strip()]
    # Hard guard: YOLO stays primary even if config is edited incorrectly.
    source_priority = [x for x in source_priority if x != "yolo"]
    source_priority.insert(0, "yolo")
    cross_bonus = float(app_config.get("detection.cross_source_confidence_bonus") or 0)
    frigate_events = [
        ev for ev in (mqtt_events or []) if str((ev or {}).get("source") or "").strip().lower() == "frigate"
    ]
    frigate_events = _frigate_events_camera_scoped(
        frigate_events,
        app_config,
        triggered_camera=triggered_camera,
    )
    frigate_events_for_merge = [ev for ev in frigate_events if not ev.get("_frigate_merge_suppressed")]
    # Safe-by-default: Frigate stays fallback-only unless explicitly enabled in config
    # or camera_tuning_by_role.frigate_site (species authority / standalone).
    from visit_contract import role_detection_flag

    standalone_on = role_detection_flag(
        app_config,
        "frigate_standalone_when_no_yolo",
        camera_id=triggered_camera,
        default=False,
    )
    standalone_no_species = role_detection_flag(
        app_config,
        "frigate_standalone_when_no_accepted_species",
        camera_id=triggered_camera,
        default=False,
    )
    require_blind = role_detection_flag(
        app_config,
        "frigate_standalone_require_blind_yolo",
        camera_id=triggered_camera,
        default=bool(app_config.get("detection.frigate_standalone_require_blind_yolo", False)),
        opt_in=False,
    )
    blind_score_threshold = float(app_config.get("detection.frigate_standalone_blind_score_threshold", 0.7) or 0.7)
    force_after_no_yolo_s = float(
        app_config.get("detection.frigate_standalone_force_after_no_yolo_seconds", 12.0) or 12.0
    )
    force_after_no_yolo_s = max(1.0, min(force_after_no_yolo_s, 300.0))
    has_accepted_species = _prepared_has_accepted_species(prepared)
    effective_blind_score = float(yolo_blind_score)
    if bool(yolo_blind_confirmed) and effective_blind_score <= 0.0:
        effective_blind_score = 1.0
    blind_gate_ok = (
        bool(yolo_blind_confirmed and effective_blind_score >= blind_score_threshold) if require_blind else True
    )
    session_duration_s = max(0.0, float((end_time - start_time).total_seconds()))
    forced_standalone_due_no_yolo = (
        standalone_on and bool(frigate_events) and not prepared and session_duration_s >= force_after_no_yolo_s
    )
    if require_blind and not blind_gate_ok and forced_standalone_due_no_yolo:
        blind_gate_ok = True
        logger.warning(
            "Fusion: forcing Frigate standalone after %.1fs with no YOLO rows "
            "(require_blind_yolo=true, blind_confirmed=%s, blind_score=%.3f)",
            session_duration_s,
            bool(yolo_blind_confirmed),
            effective_blind_score,
        )
    want_standalone = (
        standalone_on
        and bool(frigate_events)
        and (not prepared or (standalone_no_species and not has_accepted_species))
        and blind_gate_ok
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
            elif standalone_no_species and not has_accepted_species:
                # Rescue mode: YOLO produced only weak/review rows, keep Frigate standalone
                # as primary clip-level evidence so fallback cannot be silently suppressed.
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
    from visit_contract import frigate_species_authority as _frigate_species_authority

    fused = merge_detections(
        prepared,
        frigate_events_for_merge,
        start_time,
        end_time,
        merge_window,
        dedup_window,
        one_per_species=one_per_species,
        one_per_species_keep_distinct_tracks=one_per_species_keep_distinct_tracks,
        source_priority=source_priority,
        cross_source_confidence_bonus=cross_bonus,
        species_mapping=_species_mapping(app_config),
        absorb_generic_bird=bool(app_config.get("detection.absorb_generic_bird", True)),
        absorb_generic_bird_overlap_min_sec=float(
            app_config.get("detection.absorb_generic_bird_overlap_min_sec") or 0.1
        ),
        absorb_generic_bird_min_classifier_confidence=config_float(
            app_config,
            "detection.absorb_generic_bird_min_classifier_confidence",
            ABSORB_GENERIC_BIRD_MIN_CLASSIFIER_CONFIDENCE,
        ),
        preserve_equal_rank_conflicts_for_arbitration=True,
        frigate_species_authority=_frigate_species_authority(
            app_config, camera_id=triggered_camera
        ),
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
    fused = apply_weighted_species_arbiter(
        fused,
        mqtt_events=mqtt_events,
        app_config=app_config,
        camera_id=triggered_camera,
    )
    if bool(app_config.get("detection.hypothesis_arbitration_enabled", False)):
        fused = apply_hypothesis_arbitration(fused)
    fused = _merge_adjacent_yolo_fragments(fused, app_config)
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
    out = [
        d
        for d in fused
        if passes_binary_track_first_store_floor(
            app_config=app_config,
            row=d,
            min_conf_store=min_conf_store,
        )
    ]
    if len(out) < len(fused):
        logger.info(
            "Fusion: dropped %s row(s) below min_confidence_to_store=%s",
            len(fused) - len(out),
            min_conf_store,
        )
    return out
