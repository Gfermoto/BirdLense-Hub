"""Deferred species classification at finalize (linear pipeline stage classify_enrich)."""

from __future__ import annotations

import logging
import time
from typing import Any

from linear_pipeline import is_linear_pipeline
from processor_config_defaults import (
    CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    config_float,
)

logger = logging.getLogger(__name__)

# Wall-clock cap for deferred classify at finalize (multiple hires crops + ONNX).
DEFAULT_CLASSIFIER_FINALIZE_MAX_RUNTIME_MS = 2500.0

_UNKNOWN_SPECIES = frozenset({"", "bird", "unknown", "unknown bird"})


def defer_classifier_to_finalize(app_config) -> bool:
    if not is_linear_pipeline(app_config):
        return False
    raw = app_config.get("processor.classifier_defer_to_finalize")
    if raw is None:
        return True
    return bool(raw)


def _finalize_max_runtime_ms(app_config) -> float:
    try:
        raw = app_config.get("processor.classifier_finalize_max_runtime_ms")
        if raw is None:
            return DEFAULT_CLASSIFIER_FINALIZE_MAX_RUNTIME_MS
        return max(50.0, float(raw))
    except (TypeError, ValueError):
        return DEFAULT_CLASSIFIER_FINALIZE_MAX_RUNTIME_MS


def _finalize_max_tracks(app_config) -> int:
    """Top-N eligible tracks by best_frame_score; 0 = no limit."""
    try:
        raw = app_config.get("processor.classifier_finalize_max_tracks")
        if raw is None:
            return 2
        return max(0, min(32, int(raw)))
    except (TypeError, ValueError):
        return 2


def _finalize_max_key_frames(app_config) -> int:
    try:
        raw = app_config.get("processor.classifier_finalize_max_key_frames")
        if raw is None:
            return 1
        return max(1, min(8, int(raw)))
    except (TypeError, ValueError):
        return 1


def _track_has_bird_detector(track: dict[str, Any]) -> bool:
    return any(
        str((ev or {}).get("label") or "").strip().lower() == "bird"
        for ev in (track.get("detector_events") or [])
        if isinstance(ev, dict)
    )


def _unknown_labels(app_config) -> set[str]:
    unknown = str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird").strip().lower()
    return set(_UNKNOWN_SPECIES) | {unknown}


def _collect_lores_crops(
    track: dict[str, Any],
    *,
    max_kf: int,
) -> list[tuple[Any, float, str]]:
    crops: list[tuple[Any, float, str]] = []
    best = track.get("best_frame")
    if best is not None:
        crops.append((best, float(track.get("best_frame_score") or 0.0), "best_frame_lores"))
    for kf in (track.get("key_frames") or [])[:max_kf]:
        if not isinstance(kf, dict):
            continue
        crop = kf.get("crop")
        if crop is None:
            continue
        crops.append((crop, float(kf.get("score") or 0.0), "key_frame_lores"))
    return crops


def enrich_tracks_classifier_at_finalize(
    tracks: dict[int | str, dict[str, Any]],
    strategy: Any,
    app_config,
    *,
    video_path: str | None = None,
    camera_id: str | None = None,
) -> int:
    """
    Run Birder on key crops per track. Returns count of classifier events appended.

    Architecture (dual-stream):
      detect/track on lores → bbox remapped to record → classify on crops.
      Prefer **in-memory lores** first (no NVDEC contention with live YOLO), then
      record_hires for sharper crops when budget remains.

    Latency: wall-clock ``processor.classifier_finalize_max_runtime_ms`` stops more tracks;
    ``classifier_finalize_max_tracks`` keeps only top-N by best_frame_score.
    """
    if not defer_classifier_to_finalize(app_config):
        return 0
    if not tracks:
        return 0
    if strategy is None or not hasattr(strategy, "_classify_crop"):
        return 0

    max_kf = _finalize_max_key_frames(app_config)
    min_guess = config_float(
        app_config,
        "processor.classifier_best_guess_min_confidence",
        CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    )
    max_runtime_ms = _finalize_max_runtime_ms(app_config)
    max_tracks = _finalize_max_tracks(app_config)
    unknown_labels = _unknown_labels(app_config)
    started = time.perf_counter()
    deadline_mono = started + (max_runtime_ms / 1000.0)
    runtime_cfg = getattr(app_config, "config", None) or app_config
    crop_mode = "record_hires"
    pad_frac = 0.06
    try:
        from record_hires_crop import (
            resolve_crop_pad_frac,
            resolve_enrichment_crop,
            resolve_enrichment_crop_source,
            track_as_detection,
        )

        crop_mode = resolve_enrichment_crop_source(
            app_config,
            config_key="processor.classifier_crop_source",
            default="record_hires",
        )
        pad_frac = resolve_crop_pad_frac(app_config)
    except ImportError:
        resolve_enrichment_crop = None  # type: ignore[assignment,misc]
        track_as_detection = None  # type: ignore[assignment,misc]

    eligible: list[tuple[Any, dict[str, Any]]] = []
    for track_id, track in tracks.items():
        if not isinstance(track, dict):
            continue
        if track.get("classifier_events"):
            continue
        if not _track_has_bird_detector(track):
            continue
        eligible.append((track_id, track))

    def _score(item: tuple[Any, dict[str, Any]]) -> float:
        try:
            return float(item[1].get("best_frame_score") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    eligible.sort(key=_score, reverse=True)
    if max_tracks > 0:
        skipped = max(0, len(eligible) - max_tracks)
        eligible = eligible[:max_tracks]
        if skipped:
            logger.info(
                "classifier finalize: max_tracks=%s skipped=%s kept=%s",
                max_tracks,
                skipped,
                len(eligible),
            )

    appended = 0
    timed_out = False
    no_crop_tracks = 0
    classify_errors = 0
    low_conf_skips = 0
    unknown_skips = 0

    for track_id, track in eligible:
        if time.perf_counter() >= deadline_mono:
            timed_out = True
            break

        crops: list[tuple[Any, float, str]] = []

        # 1) Prefer in-memory lores — avoid NVDEC/CUDA contention with live detect.
        crops.extend(_collect_lores_crops(track, max_kf=max_kf))

        # 2) Optional hires upgrade when budget remains (sharper crop).
        if (
            resolve_enrichment_crop is not None
            and track_as_detection is not None
            and video_path
            and time.perf_counter() < deadline_mono
        ):
            try:
                det_like = track_as_detection(track, camera_id=camera_id)
                hires_crop, src = resolve_enrichment_crop(
                    det_like,
                    video_path=video_path,
                    mode=crop_mode,
                    lores_crop=track.get("best_frame"),
                    pad_frac=pad_frac,
                    runtime_cfg=runtime_cfg,
                    prefer_lores=False,
                    deadline_mono=deadline_mono,
                )
            except Exception:
                logger.warning(
                    "finalize hires crop failed track=%s",
                    track_id,
                    exc_info=True,
                )
                hires_crop, src = None, None
            if hires_crop is not None:
                score = float(track.get("best_frame_score") or 0.0)
                if src == "record_hires":
                    score += 0.5  # slight preference after lores attempts
                crops.append((hires_crop, score, src or "record_hires"))

        if not crops:
            no_crop_tracks += 1
            continue

        # Lores first by source, then by score within each group.
        def _crop_order(item: tuple[Any, float, str]) -> tuple[int, float]:
            _crop, score, src = item
            lores_rank = 0 if "lores" in str(src) else 1
            return (lores_rank, -float(score))

        crops.sort(key=_crop_order)
        seen = 0
        named_appended_for_track = 0
        for crop, _score, crop_src in crops:
            if time.perf_counter() >= deadline_mono:
                timed_out = True
                break
            if seen >= max_kf:
                break
            try:
                out = strategy._classify_crop(crop)
            except Exception:
                classify_errors += 1
                logger.warning(
                    "finalize classify crop failed track=%s src=%s",
                    track_id,
                    crop_src,
                    exc_info=True,
                )
                continue
            if out is None or not getattr(out, "species_name", None):
                continue
            species = str(out.species_name).strip()
            try:
                det_conf = max(
                    float(ev.get("confidence") or 0.0)
                    for ev in (track.get("detector_events") or [])
                    if isinstance(ev, dict)
                )
            except ValueError:
                det_conf = 0.0
            cls_conf = float(
                getattr(out, "top1_confidence", None)
                if getattr(out, "top1_confidence", None) is not None
                else getattr(out, "confidence", 0.0) or 0.0
            )
            if species.lower() in unknown_labels:
                unknown_skips += 1
                seen += 1
                # Keep searching other crops for a named species.
                continue
            if cls_conf < min_guess:
                low_conf_skips += 1
                if low_conf_skips <= 8:
                    logger.info(
                        "finalize classify low_conf track=%s species=%s conf=%.3f min_guess=%.3f src=%s",
                        track_id,
                        species,
                        cls_conf,
                        min_guess,
                        crop_src,
                    )
                seen += 1
                continue
            track.setdefault("classifier_events", []).append(
                {
                    "species_name": species,
                    "confidence": cls_conf,
                    "detector_confidence": det_conf,
                    "combined_confidence": det_conf * cls_conf,
                    "entropy": getattr(out, "entropy", None),
                    "top1_top2_margin": getattr(out, "top1_top2_margin", None),
                    "t": track.get("end_time"),
                    "source": "finalize_deferred",
                    "crop_source": crop_src,
                }
            )
            appended += 1
            named_appended_for_track += 1
            seen += 1
            # One strong named hit is enough per track under tight budget.
            if named_appended_for_track >= 1 and time.perf_counter() >= (deadline_mono - 0.15):
                break
        if timed_out:
            break

    if timed_out:
        logger.info(
            "Linear pipeline: deferred classifier hit max_runtime_ms=%.0f (appended=%s)",
            max_runtime_ms,
            appended,
        )
    elif appended:
        logger.info("Linear pipeline: deferred classifier appended %s event(s)", appended)
    else:
        logger.info(
            "Linear pipeline: deferred classifier appended 0 "
            "(eligible=%s no_crop=%s classify_errors=%s low_conf=%s unknown=%s runtime_ms=%.0f)",
            len(eligible),
            no_crop_tracks,
            classify_errors,
            low_conf_skips,
            unknown_skips,
            (time.perf_counter() - started) * 1000.0,
        )
    return appended
