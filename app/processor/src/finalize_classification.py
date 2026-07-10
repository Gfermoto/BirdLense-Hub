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
      detect/track on lores → bbox remapped to record → classify on **record_hires** crop.
      Lores best_frame/key_frames are fallback only when hires seek fails.

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
            logger.debug(
                "classifier finalize: max_tracks=%s skipped=%s kept=%s",
                max_tracks,
                skipped,
                len(eligible),
            )

    appended = 0
    timed_out = False
    for track_id, track in eligible:
        if time.perf_counter() >= deadline_mono:
            timed_out = True
            break

        crops: list[tuple[Any, float, str]] = []

        # 1) Primary: record_hires (scaled bbox on main MP4) — dual-stream contract.
        if resolve_enrichment_crop is not None and track_as_detection is not None and video_path:
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
            if hires_crop is not None:
                score = float(track.get("best_frame_score") or 0.0)
                if src == "record_hires":
                    score += 1.0  # prefer hires when sorting
                crops.append((hires_crop, score, src))

        # 2) Fallback only: in-memory lores (if hires missing/failed).
        if not crops:
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

        if not crops:
            continue
        crops.sort(key=lambda x: x[1], reverse=True)
        seen = 0
        for crop, _score, crop_src in crops:
            if time.perf_counter() >= deadline_mono:
                timed_out = True
                break
            if seen >= max_kf:
                break
            try:
                out = strategy._classify_crop(crop)
            except Exception:
                logger.debug("finalize classify crop failed track=%s", track_id, exc_info=True)
                continue
            if out is None or not getattr(out, "species_name", None):
                continue
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
            if cls_conf < min_guess:
                continue
            track.setdefault("classifier_events", []).append(
                {
                    "species_name": str(out.species_name),
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
            seen += 1
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
    return appended
