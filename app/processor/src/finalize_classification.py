"""Deferred species classification at finalize (linear pipeline stage classify_enrich)."""

from __future__ import annotations

import logging
from typing import Any

from linear_pipeline import is_linear_pipeline
from processor_config_defaults import (
    CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    config_float,
)

logger = logging.getLogger(__name__)


def defer_classifier_to_finalize(app_config) -> bool:
    if not is_linear_pipeline(app_config):
        return False
    raw = app_config.get("processor.classifier_defer_to_finalize")
    if raw is None:
        return True
    return bool(raw)


def enrich_tracks_classifier_at_finalize(
    tracks: dict[int | str, dict[str, Any]],
    strategy: Any,
    app_config,
    *,
    video_path: str | None = None,
    camera_id: str | None = None,
) -> int:
    """
    Run Birder on in-memory key_frames / best_frame per track.
    Returns count of classifier events appended.
    """
    if not defer_classifier_to_finalize(app_config):
        return 0
    if strategy is None or not hasattr(strategy, "_classify_crop"):
        return 0

    try:
        max_kf = int(app_config.get("processor.classifier_finalize_max_key_frames") or 3)
    except (TypeError, ValueError):
        max_kf = 3
    max_kf = max(1, min(8, max_kf))
    min_guess = config_float(
        app_config,
        "processor.classifier_best_guess_min_confidence",
        CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    )
    runtime_cfg = getattr(app_config, "config", None) or app_config
    crop_mode = "auto"
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
            default="auto",
        )
        pad_frac = resolve_crop_pad_frac(app_config)
    except ImportError:
        resolve_enrichment_crop = None  # type: ignore[assignment,misc]
        track_as_detection = None  # type: ignore[assignment,misc]

    appended = 0
    for track_id, track in tracks.items():
        if not isinstance(track, dict):
            continue
        if track.get("classifier_events"):
            continue
        bird_det = any(
            str((ev or {}).get("label") or "").strip().lower() == "bird"
            for ev in (track.get("detector_events") or [])
            if isinstance(ev, dict)
        )
        if not bird_det:
            continue

        crops: list[tuple[Any, float, str]] = []
        if resolve_enrichment_crop is not None and track_as_detection is not None and video_path:
            det_like = track_as_detection(track, camera_id=camera_id)
            hires_crop, src = resolve_enrichment_crop(
                det_like,
                video_path=video_path,
                mode=crop_mode,
                lores_crop=track.get("best_frame"),
                pad_frac=pad_frac,
                runtime_cfg=runtime_cfg,
            )
            if hires_crop is not None:
                crops.append((hires_crop, float(track.get("best_frame_score") or 0.0), src))
        best = track.get("best_frame")
        if best is not None and not crops:
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
                else getattr(out, "confidence", 0.0)
                or 0.0
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

    if appended:
        logger.info("Linear pipeline: deferred classifier appended %s event(s)", appended)
    return appended
