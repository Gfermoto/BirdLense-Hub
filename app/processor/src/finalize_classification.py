"""Deferred species classification at finalize (linear pipeline stage classify_enrich)."""

from __future__ import annotations

import logging
import time
from typing import Any

from linear_pipeline import is_linear_pipeline
from processor_config_defaults import (
    CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    CLASSIFIER_SOFT_EVENTS_ENABLED,
    CLASSIFIER_SOFT_MIN_CONFIDENCE,
    config_float,
)

logger = logging.getLogger(__name__)

# Defaults aligned with default_config.yaml (lores+hires budget on Orin).
DEFAULT_CLASSIFIER_FINALIZE_MAX_RUNTIME_MS = 8000.0
DEFAULT_CLASSIFIER_FINALIZE_MAX_TRACKS = 6
DEFAULT_CLASSIFIER_FINALIZE_MAX_KEY_FRAMES = 3

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
            return DEFAULT_CLASSIFIER_FINALIZE_MAX_TRACKS
        return max(0, min(32, int(raw)))
    except (TypeError, ValueError):
        return DEFAULT_CLASSIFIER_FINALIZE_MAX_TRACKS


def _finalize_max_key_frames(app_config) -> int:
    try:
        raw = app_config.get("processor.classifier_finalize_max_key_frames")
        if raw is None:
            return DEFAULT_CLASSIFIER_FINALIZE_MAX_KEY_FRAMES
        return max(1, min(8, int(raw)))
    except (TypeError, ValueError):
        return DEFAULT_CLASSIFIER_FINALIZE_MAX_KEY_FRAMES


def _track_has_bird_detector(track: dict[str, Any]) -> bool:
    return any(
        str((ev or {}).get("label") or "").strip().lower() == "bird"
        for ev in (track.get("detector_events") or [])
        if isinstance(ev, dict)
    )


def _unknown_labels(app_config) -> set[str]:
    unknown = str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird").strip().lower()
    return set(_UNKNOWN_SPECIES) | {unknown}


def _maybe_append_prior_topk_soft(
    track: dict[str, Any],
    out: Any,
    *,
    det_conf: float,
    event_source: str | None,
    crop_src: str,
    unknown_labels: set[str],
    soft_min: float,
    track_id: Any,
    primary_species: str | None = None,
) -> int:
    """Append soft top-k named when site prior applies (confusion rescue)."""
    primary = str(primary_species or "").strip().lower()
    candidates: list[tuple[str, float]] = []
    top_named = getattr(out, "top_named", None) or []
    for row in top_named:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        name = str(row[0] or "").strip()
        try:
            conf = float(row[1])
        except (TypeError, ValueError):
            continue
        if name:
            candidates.append((name, conf))
    ru = str(getattr(out, "runner_up_species_name", None) or "").strip()
    if ru:
        try:
            ru_conf = float(getattr(out, "runner_up_confidence", None) or 0.0)
        except (TypeError, ValueError):
            ru_conf = 0.0
        if not any(n.lower() == ru.lower() for n, _ in candidates):
            candidates.append((ru, ru_conf))

    added = 0
    seen_names = {
        str(ev.get("species_name") or "").strip().lower()
        for ev in (track.get("classifier_events") or [])
        if isinstance(ev, dict)
    }
    def _fold(s: str) -> str:
        return " ".join(str(s or "").strip().lower().replace("-", " ").split())

    _COLUMBIDAE = {
        "common wood pigeon",
        "eurasian collared dove",
        "stock dove",
        "european turtle dove",
    }
    primary_is_columbidae = _fold(primary) in _COLUMBIDAE
    try:
        from processor_support import get_data_dir
        from site_adapter import adjust_confidence_with_site_adapter

        data_dir = get_data_dir()
    except Exception:
        data_dir = None
        candidates = list(candidates)

    if data_dir is None:
        return 0

    for name, conf in candidates:
        if not name or name.lower() in unknown_labels:
            continue
        if name.lower() == primary:
            continue
        if name.lower() in seen_names:
            continue
        # Prior soft: require real near-miss mass (no 0.001 long-tail invent).
        conf_floor = max(soft_min, 0.05)
        try:
            _probe_adj, _probe_info = adjust_confidence_with_site_adapter(
                data_dir=data_dir,
                species=name,
                confidence=max(conf, soft_min),
                track_id=track_id,
            )
            if _probe_info.get("applied") and float(_probe_info.get("delta") or 0.0) > 0:
                # Uncertain top1 (low margin): allow slightly weaker prior near-miss.
                margin = getattr(out, "top1_top2_margin", None)
                try:
                    margin_f = float(margin) if margin is not None else 1.0
                except (TypeError, ValueError):
                    margin_f = 1.0
                conf_floor = 0.04 if margin_f < 0.08 else 0.06
                # #2 columbidae under pigeon/dove: prior-backed near-miss (even high margin).
                if (
                    primary_is_columbidae
                    and _fold(name) in _COLUMBIDAE
                    and _fold(name) != _fold(primary)
                ):
                    coli = sorted(
                        ((n0, float(c0)) for n0, c0 in candidates if _fold(n0) in _COLUMBIDAE),
                        key=lambda t: t[1],
                        reverse=True,
                    )
                    rank = next(
                        (i for i, (n0, _) in enumerate(coli) if _fold(n0) == _fold(name)),
                        99,
                    )
                    if rank == 1:
                        # Collared-dove under hard pigeon: track crops often show dove@~0.002-0.004.
                        if (
                            _fold(primary) == "common wood pigeon"
                            and _fold(name) == "eurasian collared dove"
                        ):
                            conf_floor = min(conf_floor, 0.002)
                        elif margin_f < 0.15:
                            conf_floor = min(conf_floor, 0.015)
        except Exception:
            pass
        if conf < conf_floor:
            continue
        # Skip injecting unrelated priors onto pigeon clips (avoid false Fieldfare wins).
        if primary_is_columbidae and _fold(name) not in _COLUMBIDAE:
            # Still allow non-columbidae only when present in model top_named (real mass).
            in_topk = any(
                _fold(str(r[0])) == _fold(name)
                for r in (getattr(out, "top_named", None) or [])
                if isinstance(r, (list, tuple)) and r
            )
            if not in_topk:
                continue
        try:
            _adj, info = adjust_confidence_with_site_adapter(
                data_dir=data_dir,
                species=name,
                confidence=conf,
                track_id=track_id,
            )
            if not info.get("applied") or float(info.get("delta") or 0.0) <= 0:
                continue
            # Keep raw conf; linear prior re-rank applies delta once.
        except Exception:
            continue
        track.setdefault("classifier_events", []).append(
            {
                "species_name": name,
                "confidence": conf,
                "detector_confidence": det_conf,
                "combined_confidence": det_conf * conf,
                "entropy": getattr(out, "entropy", None),
                "top1_top2_margin": getattr(out, "top1_top2_margin", None),
                "t": track.get("end_time"),
                "source": str(event_source or "finalize_deferred"),
                "crop_source": crop_src,
                "soft": True,
                "soft_reason": "topk_prior",
            }
        )
        seen_names.add(name.lower())
        added += 1
    return added


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


def _empty_finalize_outcome(*, reason: str = "skipped") -> dict[str, Any]:
    return {
        "appended": 0,
        "eligible": 0,
        "skipped_budget": 0,
        "no_crop": 0,
        "classify_errors": 0,
        "low_conf": 0,
        "unknown": 0,
        "timed_out": False,
        "runtime_ms": 0.0,
        "skip_reason": reason,
    }


def enrich_tracks_classifier_at_finalize(
    tracks: dict[int | str, dict[str, Any]],
    strategy: Any,
    app_config,
    *,
    video_path: str | None = None,
    camera_id: str | None = None,
    track_ids: set[Any] | frozenset[Any] | None = None,
    max_runtime_ms: float | None = None,
    max_tracks: int | None = None,
    event_source: str = "finalize_deferred",
    require_defer_enabled: bool = True,
) -> dict[str, Any]:
    """
    Run Birder on key crops per track.

    Returns outcome counters for ``recording_session_summary``:
    ``appended``, ``eligible``, ``skipped_budget``, ``no_crop``, ``classify_errors``,
    ``low_conf``, ``unknown``, ``timed_out``, ``runtime_ms``.

    Architecture (dual-stream):
      detect/track on lores → bbox remapped to record → classify on crops.
      Prefer **in-memory lores** first (no NVDEC contention with live YOLO), then
      record_hires for sharper crops when budget remains.

    Latency: wall-clock ``processor.classifier_finalize_max_runtime_ms`` stops more tracks;
    ``classifier_finalize_max_tracks`` keeps only top-N by best_frame_score.

    Async patch path may pass ``track_ids`` / ``max_runtime_ms`` / ``max_tracks``
    overrides and ``require_defer_enabled=False``.
    """
    if require_defer_enabled and not defer_classifier_to_finalize(app_config):
        return _empty_finalize_outcome(reason="defer_disabled")
    if not tracks:
        return _empty_finalize_outcome(reason="no_tracks")
    if strategy is None or not hasattr(strategy, "_classify_crop"):
        return _empty_finalize_outcome(reason="no_strategy")

    max_kf = _finalize_max_key_frames(app_config)
    min_guess = config_float(
        app_config,
        "processor.classifier_best_guess_min_confidence",
        CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    )
    soft_raw = app_config.get("processor.classifier_soft_events_enabled")
    soft_enabled = (
        CLASSIFIER_SOFT_EVENTS_ENABLED if soft_raw is None else bool(soft_raw)
    )
    soft_min = config_float(
        app_config,
        "processor.classifier_soft_min_confidence",
        CLASSIFIER_SOFT_MIN_CONFIDENCE,
    )
    if max_runtime_ms is None:
        max_runtime_ms = _finalize_max_runtime_ms(app_config)
    else:
        max_runtime_ms = float(max_runtime_ms)
    if max_tracks is None:
        max_tracks = _finalize_max_tracks(app_config)
    else:
        max_tracks = int(max_tracks)
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

    filter_ids: set[str] | None = None
    if track_ids is not None:
        filter_ids = {str(x) for x in track_ids if x is not None}

    eligible: list[tuple[Any, dict[str, Any]]] = []
    for track_id, track in tracks.items():
        if not isinstance(track, dict):
            continue
        if filter_ids is not None and str(track_id) not in filter_ids:
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
    skipped_budget = 0
    if max_tracks > 0:
        skipped_budget = max(0, len(eligible) - max_tracks)
        for _tid, skipped_track in eligible[max_tracks:]:
            skipped_track["classify_skip_reason"] = "budget"
        eligible = eligible[:max_tracks]
        if skipped_budget:
            logger.info(
                "classifier finalize: max_tracks=%s skipped=%s kept=%s",
                max_tracks,
                skipped_budget,
                len(eligible),
            )

    appended = 0
    timed_out = False
    no_crop_tracks = 0
    classify_errors = 0
    low_conf_skips = 0
    unknown_skips = 0
    eligible_count = len(eligible)

    for track_id, track in eligible:
        if time.perf_counter() >= deadline_mono:
            timed_out = True
            track["classify_skip_reason"] = track.get("classify_skip_reason") or "timeout"
            # Mark remaining not-yet-processed tracks as timeout.
            rest = False
            for rest_id, rest_track in eligible:
                if rest_id == track_id:
                    rest = True
                if rest:
                    rest_track["classify_skip_reason"] = rest_track.get("classify_skip_reason") or "timeout"
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
            track["classify_skip_reason"] = "no_crop"
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
                alt = getattr(out, "alt_species_name", None)
                alt_s = str(alt or "").strip()
                alt_conf_raw = getattr(out, "alt_confidence", None)
                try:
                    alt_conf = float(alt_conf_raw) if alt_conf_raw is not None else float(cls_conf)
                except (TypeError, ValueError):
                    alt_conf = float(cls_conf)
                # Site-prior species: keep weaker alts (rescue Unknown→named for canary).
                prior_floor = soft_min
                if soft_enabled and alt_s:
                    try:
                        from processor_support import get_data_dir
                        from site_adapter import adjust_confidence_with_site_adapter

                        _adj, _ainfo = adjust_confidence_with_site_adapter(
                            data_dir=get_data_dir(),
                            species=alt_s,
                            confidence=alt_conf,
                            track_id=track_id,
                        )
                        if _ainfo.get("applied") and float(_ainfo.get("delta") or 0.0) > 0:
                            prior_floor = min(soft_min, 0.005)
                            alt_conf = float(_adj)
                    except Exception:
                        pass
                if (
                    soft_enabled
                    and alt_s
                    and alt_s.lower() not in unknown_labels
                    and alt_conf >= prior_floor
                ):
                    track.setdefault("classifier_events", []).append(
                        {
                            "species_name": alt_s,
                            "confidence": alt_conf,
                            "detector_confidence": det_conf,
                            "combined_confidence": det_conf * alt_conf,
                            "entropy": getattr(out, "entropy", None),
                            "top1_top2_margin": getattr(out, "top1_top2_margin", None),
                            "t": track.get("end_time"),
                            "source": str(event_source or "finalize_deferred"),
                            "crop_source": crop_src,
                            "soft": True,
                            "soft_reason": "unknown_alt_argmax",
                        }
                    )
                    appended += 1
                elif soft_enabled and unknown_skips < 4:
                    logger.info(
                        "finalize soft_skip track=%s alt=%s alt_conf=%.4f floor=%.4f src=%s",
                        track_id,
                        alt_s or None,
                        alt_conf,
                        prior_floor,
                        crop_src,
                    )
                # Unknown: soft-append prior species that already have real top_named mass
                # (incl. dove @>=0.015). Runs before open-set invent.
                if soft_enabled and (not alt_s or alt_conf < prior_floor):
                    try:
                        from processor_support import get_data_dir
                        from site_adapter import adjust_confidence_with_site_adapter

                        data_dir = get_data_dir()
                        top_named = getattr(out, "top_named", None) or []
                        best_prior = None  # (delta, conf, display)
                        for row in top_named:
                            if not isinstance(row, (list, tuple)) or len(row) < 2:
                                continue
                            n = str(row[0] or "").strip()
                            try:
                                c = float(row[1])
                            except (TypeError, ValueError):
                                continue
                            if not n or n.lower() in unknown_labels:
                                continue
                            # Dove/pigeon: allow 0.006 when dove outranks pigeon in top_named.
                            _fold = lambda s: " ".join(str(s or "").lower().replace("-", " ").split())
                            coli = {
                                _fold(str(r[0])): float(r[1])
                                for r in top_named
                                if isinstance(r, (list, tuple)) and len(r) >= 2
                                and any(k in str(r[0]).lower() for k in ("dove", "pigeon"))
                            }
                            dove_c = coli.get("eurasian collared dove", 0.0)
                            pig_c = coli.get("common wood pigeon", 0.0)
                            min_c = 0.015
                            if _fold(n) == "eurasian collared dove" and dove_c >= pig_c and dove_c >= 0.004:
                                min_c = 0.004
                            if c < min_c:
                                continue
                            _adj, info = adjust_confidence_with_site_adapter(
                                data_dir=data_dir,
                                species=n,
                                confidence=c,
                                track_id=track_id,
                            )
                            if not info.get("applied"):
                                continue
                            delta = float(info.get("delta") or 0.0)
                            if delta < 0.10:
                                continue
                            if best_prior is None or delta > best_prior[0] or (
                                delta == best_prior[0] and c > best_prior[1]
                            ):
                                best_prior = (delta, c, n)
                        if best_prior is not None:
                            _delta, c, n = best_prior
                            track.setdefault("classifier_events", []).append(
                                {
                                    "species_name": n,
                                    "confidence": c,
                                    "detector_confidence": det_conf,
                                    "combined_confidence": det_conf * c,
                                    "entropy": getattr(out, "entropy", None),
                                    "top1_top2_margin": getattr(out, "top1_top2_margin", None),
                                    "t": track.get("end_time"),
                                    "source": str(event_source or "finalize_deferred"),
                                    "crop_source": crop_src,
                                    "soft": True,
                                    "soft_reason": "unknown_topk_prior",
                                }
                            )
                            appended += 1
                    except Exception:
                        pass
                # Open-set invent only if top_named prior soft did not already fire.
                _soft_just = any(
                    isinstance(ev, dict)
                    and ev.get("soft")
                    and ev.get("crop_source") == crop_src
                    and ev.get("soft_reason") in {"unknown_alt_argmax", "unknown_topk_prior"}
                    for ev in (track.get("classifier_events") or [])
                )
                if soft_enabled and (not alt_s or alt_conf < prior_floor) and not _soft_just:
                    try:
                        from processor_support import get_data_dir
                        from site_adapter import adjust_confidence_with_site_adapter, load_site_adapter

                        data_dir = get_data_dir()
                        # Do not invent thrush/sparrow when crop already looks columbidae.
                        _tn = getattr(out, "top_named", None) or []
                        _coli_mass = 0.0
                        for _row in _tn:
                            if not isinstance(_row, (list, tuple)) or len(_row) < 2:
                                continue
                            if any(k in str(_row[0]).lower() for k in ("dove", "pigeon")):
                                try:
                                    _coli_mass = max(_coli_mass, float(_row[1]))
                                except (TypeError, ValueError):
                                    pass
                        _peak = 0.0
                        for _row in _tn:
                            if not isinstance(_row, (list, tuple)) or len(_row) < 2:
                                continue
                            try:
                                _peak = max(_peak, float(_row[1]))
                            except (TypeError, ValueError):
                                pass
                        # Skip invent when coli mass / non-flat peak / alt already soft-accepted.
                        _skip_invent = (
                            _coli_mass >= 0.001
                            or _peak >= 0.003
                            or (bool(alt_s) and alt_conf >= prior_floor)
                        )
                        manifest = None if _skip_invent else load_site_adapter(data_dir)
                        if manifest is not None:
                            # Thrush/sparrow open-set rescue (not columbidae invent).
                            _OPEN_SET_DISPLAY = {
                                "fieldfare": "Fieldfare",
                                "mistle thrush": "Mistle Thrush",
                                "song thrush": "Song Thrush",
                                "redwing": "Redwing",
                                "house sparrow": "House Sparrow",
                                "great tit": "Great Tit",
                            }
                            ranked = sorted(
                                (
                                    (float(delta), prior_name)
                                    for prior_name, delta in manifest.priors_map().items()
                                    if prior_name in _OPEN_SET_DISPLAY and float(delta) >= 0.15
                                ),
                                reverse=True,
                            )
                            for delta, prior_name in ranked[:1]:
                                display = _OPEN_SET_DISPLAY[prior_name]
                                guess_conf = max(soft_min, 0.05)
                                adj, info = adjust_confidence_with_site_adapter(
                                    data_dir=data_dir,
                                    species=display,
                                    confidence=guess_conf,
                                    track_id=track_id,
                                )
                                if not info.get("applied"):
                                    continue
                                track.setdefault("classifier_events", []).append(
                                    {
                                        "species_name": display,
                                        "confidence": guess_conf,
                                        "detector_confidence": det_conf,
                                        "combined_confidence": det_conf * guess_conf,
                                        "entropy": getattr(out, "entropy", None),
                                        "top1_top2_margin": getattr(out, "top1_top2_margin", None),
                                        "t": track.get("end_time"),
                                        "source": str(event_source or "finalize_deferred"),
                                        "crop_source": crop_src,
                                        "soft": True,
                                        "soft_reason": "prior_open_set_guess",
                                    }
                                )
                                appended += 1
                    except Exception:
                        pass
                unknown_skips += 1
                seen += 1
                # Keep searching other crops for a named species.
                continue
            if cls_conf < min_guess:
                if soft_enabled and cls_conf >= soft_min:
                    track.setdefault("classifier_events", []).append(
                        {
                            "species_name": species,
                            "confidence": cls_conf,
                            "detector_confidence": det_conf,
                            "combined_confidence": det_conf * cls_conf,
                            "entropy": getattr(out, "entropy", None),
                            "top1_top2_margin": getattr(out, "top1_top2_margin", None),
                            "t": track.get("end_time"),
                            "source": str(event_source or "finalize_deferred"),
                            "crop_source": crop_src,
                            "soft": True,
                            "soft_reason": "below_min_guess",
                        }
                    )
                    appended += 1
                    if soft_enabled:
                        appended += _maybe_append_prior_topk_soft(
                            track,
                            out,
                            det_conf=det_conf,
                            event_source=event_source,
                            crop_src=crop_src,
                            unknown_labels=unknown_labels,
                            soft_min=soft_min,
                            track_id=track_id,
                            primary_species=species,
                        )
                else:
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
                    "source": str(event_source or "finalize_deferred"),
                    "crop_source": crop_src,
                }
            )
            appended += 1
            if soft_enabled:
                appended += _maybe_append_prior_topk_soft(
                    track,
                    out,
                    det_conf=det_conf,
                    event_source=event_source,
                    crop_src=crop_src,
                    unknown_labels=unknown_labels,
                    soft_min=soft_min,
                    track_id=track_id,
                    primary_species=species,
                )
            named_appended_for_track += 1
            seen += 1
            # One strong named hit is enough per track under tight budget.
            if named_appended_for_track >= 1 and time.perf_counter() >= (deadline_mono - 0.15):
                break
        if timed_out:
            break

    runtime_ms = round(max(0.0, (time.perf_counter() - started) * 1000.0), 3)
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
            eligible_count,
            no_crop_tracks,
            classify_errors,
            low_conf_skips,
            unknown_skips,
            runtime_ms,
        )
    return {
        "appended": int(appended),
        "eligible": int(eligible_count),
        "skipped_budget": int(skipped_budget),
        "no_crop": int(no_crop_tracks),
        "classify_errors": int(classify_errors),
        "low_conf": int(low_conf_skips),
        "unknown": int(unknown_skips),
        "timed_out": bool(timed_out),
        "runtime_ms": runtime_ms,
        "skip_reason": None,
    }
