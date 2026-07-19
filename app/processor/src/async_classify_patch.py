"""RC2: async classify leftovers after persist → patch visit (opt-in).

Default off. When enabled, leftover tracks with classify_skip_reason in
{budget, timeout, deferred} are queued after create_video. Worker:

1. Re-runs Birder on leftover track crops (second budget).
2. PATCHes named results via create_video ``detections`` track map +
   ``API.enrich_video_detection``.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Mapping

logger = logging.getLogger(__name__)

SKIP_REASONS = frozenset({"budget", "timeout", "deferred"})
_GENERIC = frozenset({"", "bird", "unknown", "unknown bird", "птица"})
_ASYNC_CLASSIFY_LOCK = threading.Lock()


@dataclass
class AsyncClassifyPatchJob:
    video_id: int
    camera_id: str | None
    video_path: str | None
    leftovers: list[dict[str, Any]] = field(default_factory=list)
    track_map: list[dict[str, Any]] = field(default_factory=list)
    leftover_tracks: dict[Any, dict[str, Any]] = field(default_factory=dict)
    strategy: Any | None = None
    app_config: Any | None = None
    max_runtime_ms: float = 4000.0
    api: Any | None = None


_pending: list[AsyncClassifyPatchJob] = []
_lock = threading.Lock()


def async_classify_patch_enabled(app_config: Any) -> bool:
    raw = app_config.get("processor.async_classify_patch_enabled")
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def async_classify_patch_max_runtime_ms(app_config: Any) -> float:
    raw = app_config.get("processor.async_classify_patch_max_runtime_ms")
    if raw is None:
        return 4000.0
    try:
        return max(250.0, float(raw))
    except (TypeError, ValueError):
        return 4000.0


def leftover_tracks_for_async_patch(
    decisions: list[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Select persist rows that skipped classify due to budget/timeout/defer."""
    out: list[dict[str, Any]] = []
    for row in decisions or []:
        if not isinstance(row, Mapping):
            continue
        skip = str(row.get("classify_skip_reason") or row.get("skip_reason") or "").strip().lower()
        if skip not in SKIP_REASONS:
            continue
        out.append(
            {
                "track_id": row.get("track_id"),
                "classify_skip_reason": skip,
                "species_name": row.get("species_name"),
                "patch_species_name": row.get("patch_species_name"),
                "confidence": row.get("confidence"),
                "decision_kind": row.get("decision_kind"),
            }
        )
    return out


def snapshot_leftover_tracks(
    session_tracks: Mapping[Any, Any] | None,
    leftovers: list[Mapping[str, Any]] | None,
) -> dict[Any, dict[str, Any]]:
    """Shallow-copy leftover tracks for async reclassify (keep crop refs)."""
    want = {
        str(row.get("track_id"))
        for row in (leftovers or [])
        if isinstance(row, Mapping) and row.get("track_id") is not None
    }
    if not want or not session_tracks:
        return {}
    out: dict[Any, dict[str, Any]] = {}
    for tid, track in session_tracks.items():
        if str(tid) not in want:
            continue
        if not isinstance(track, dict):
            continue
        # Shallow copy: best_frame / key_frames stay shared read-only for classify.
        snap = dict(track)
        snap.pop("classifier_events", None)
        snap.pop("classify_skip_reason", None)
        out[tid] = snap
    return out


def _is_named_species(name: Any) -> bool:
    return str(name or "").strip().lower() not in _GENERIC


def _detection_id_for_track(track_map: list[dict[str, Any]], track_id: Any) -> int | None:
    try:
        tid = int(track_id)
    except (TypeError, ValueError):
        return None
    for row in track_map or []:
        if not isinstance(row, Mapping):
            continue
        try:
            if int(row.get("track_id")) != tid:
                continue
        except (TypeError, ValueError):
            continue
        try:
            return int(row["id"])
        except (TypeError, ValueError, KeyError):
            return None
    return None


def _named_from_track(track: Mapping[str, Any] | None) -> tuple[str | None, float | None]:
    if not isinstance(track, Mapping):
        return None, None
    best_name = None
    best_conf = None
    for ev in track.get("classifier_events") or []:
        if not isinstance(ev, Mapping):
            continue
        name = str(ev.get("species_name") or "").strip()
        if not _is_named_species(name):
            continue
        try:
            conf = float(ev.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        if best_conf is None or conf > best_conf:
            best_name, best_conf = name, conf
    return best_name, best_conf


def enqueue_async_classify_patch(
    *,
    app_config: Any,
    video_id: Any,
    camera_id: str | None,
    video_path: str | None,
    decisions: list[Mapping[str, Any]] | None,
    track_map: list[Mapping[str, Any]] | None = None,
    session_tracks: Mapping[Any, Any] | None = None,
    strategy: Any | None = None,
    api: Any | None = None,
    sync: bool = False,
) -> int:
    """Enqueue leftovers when feature flag on. Returns queued leftover count.

    ``sync=True`` runs the worker inline (tests).
    """
    if not async_classify_patch_enabled(app_config):
        return 0
    try:
        vid = int(video_id)
    except (TypeError, ValueError):
        return 0
    leftovers = leftover_tracks_for_async_patch(decisions)
    if not leftovers:
        return 0
    mapped = [dict(r) for r in (track_map or []) if isinstance(r, Mapping)]
    leftover_tracks = snapshot_leftover_tracks(session_tracks, leftovers)
    job = AsyncClassifyPatchJob(
        video_id=vid,
        camera_id=camera_id,
        video_path=video_path,
        leftovers=leftovers,
        track_map=mapped,
        leftover_tracks=leftover_tracks,
        strategy=strategy,
        app_config=app_config,
        max_runtime_ms=async_classify_patch_max_runtime_ms(app_config),
        api=api,
    )
    with _lock:
        _pending.append(job)
    logger.info(
        "async_classify_patch: queued video_id=%s leftovers=%s tracks=%s track_map=%s sync=%s",
        vid,
        len(leftovers),
        len(leftover_tracks),
        len(mapped),
        sync,
    )
    if sync:
        _process_job(job)
    else:
        threading.Thread(
            target=_process_job,
            args=(job,),
            name=f"async-classify-patch-{vid}",
            daemon=True,
        ).start()
    return len(leftovers)


def pending_jobs() -> int:
    with _lock:
        return len(_pending)


def _reclassify_leftovers(job: AsyncClassifyPatchJob) -> int:
    """Second-budget Birder on leftover tracks. Returns named fills count."""
    if not job.leftover_tracks or job.strategy is None or job.app_config is None:
        return 0
    track_ids = {
        left.get("track_id")
        for left in job.leftovers
        if left.get("track_id") is not None
    }
    if not track_ids:
        return 0
    try:
        from finalize_classification import enrich_tracks_classifier_at_finalize
    except ImportError:
        return 0

    try:
        # Prefer regen lock to serialize GPU/ORT with track_regenerator; fall back local.
        try:
            from track_regenerator import _TRACK_REGEN_INFER_LOCK as infer_lock
        except Exception:
            infer_lock = _ASYNC_CLASSIFY_LOCK
        with infer_lock:
            outcome = enrich_tracks_classifier_at_finalize(
                job.leftover_tracks,
                job.strategy,
                job.app_config,
                video_path=job.video_path,
                camera_id=job.camera_id,
                track_ids=track_ids,
                max_runtime_ms=job.max_runtime_ms,
                max_tracks=max(1, len(track_ids)),
                event_source="async_classify_patch",
                require_defer_enabled=False,
            )
    except Exception:
        logger.warning(
            "async_classify_patch: reclassify failed video_id=%s",
            job.video_id,
            exc_info=True,
        )
        return 0

    filled = 0
    for left in job.leftovers:
        tid = left.get("track_id")
        track = job.leftover_tracks.get(tid)
        if track is None:
            track = job.leftover_tracks.get(str(tid))
        if track is None:
            try:
                track = job.leftover_tracks.get(int(tid))
            except (TypeError, ValueError):
                track = None
        name, conf = _named_from_track(track)
        if not name:
            continue
        left["patch_species_name"] = name
        if conf is not None:
            left["confidence"] = conf
        filled += 1
    logger.info(
        "async_classify_patch: reclassify video_id=%s filled=%s outcome=%s",
        job.video_id,
        filled,
        {k: outcome.get(k) for k in ("appended", "eligible", "timed_out", "runtime_ms")}
        if isinstance(outcome, dict)
        else None,
    )
    return filled


def _process_job(job: AsyncClassifyPatchJob) -> None:
    """Reclassify leftovers, then PATCH named results via processor enrich API."""
    try:
        _reclassify_leftovers(job)
        patched = 0
        api = job.api
        if api is not None and job.track_map:
            for left in job.leftovers:
                name = left.get("patch_species_name") or left.get("species_name")
                if not _is_named_species(name):
                    continue
                det_id = _detection_id_for_track(job.track_map, left.get("track_id"))
                if det_id is None:
                    continue
                try:
                    api.enrich_video_detection(
                        job.video_id,
                        det_id,
                        species_name=str(name).strip(),
                        confidence=left.get("confidence"),
                    )
                    patched += 1
                except Exception:
                    logger.debug(
                        "async_classify_patch: enrich failed video_id=%s det=%s",
                        job.video_id,
                        det_id,
                        exc_info=True,
                    )
        if patched:
            logger.info(
                "async_classify_patch: patched video_id=%s n=%s",
                job.video_id,
                patched,
            )
            try:
                from metrics import inc_counter

                inc_counter("async_classify_patch_applied_total", patched)
            except Exception:
                pass
        else:
            logger.info(
                "async_classify_patch: no patch video_id=%s leftovers=%s "
                "(reclassify unnamed or missing track_map/api)",
                job.video_id,
                len(job.leftovers),
            )
            try:
                from metrics import inc_counter

                inc_counter("async_classify_patch_stub_total", len(job.leftovers))
            except Exception:
                pass
    finally:
        with _lock:
            try:
                _pending.remove(job)
            except ValueError:
                pass


def reset_async_classify_patch_for_tests() -> None:
    with _lock:
        _pending.clear()
