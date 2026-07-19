"""RC2: async classify leftovers after persist → patch visit (opt-in).

Default off. When enabled, leftover tracks with classify_skip_reason in
{budget, timeout, deferred} are queued after create_video. Worker uses the
create_video ``detections`` track map + ``API.enrich_video_detection`` when a
leftover carries a named ``patch_species_name`` / ``species_name``.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Mapping

logger = logging.getLogger(__name__)

SKIP_REASONS = frozenset({"budget", "timeout", "deferred"})
_GENERIC = frozenset({"", "bird", "unknown", "unknown bird", "птица"})


@dataclass
class AsyncClassifyPatchJob:
    video_id: int
    camera_id: str | None
    video_path: str | None
    leftovers: list[dict[str, Any]] = field(default_factory=list)
    track_map: list[dict[str, Any]] = field(default_factory=list)
    api: Any | None = None


_pending: list[AsyncClassifyPatchJob] = []
_lock = threading.Lock()


def async_classify_patch_enabled(app_config: Any) -> bool:
    raw = app_config.get("processor.async_classify_patch_enabled")
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


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


def enqueue_async_classify_patch(
    *,
    app_config: Any,
    video_id: Any,
    camera_id: str | None,
    video_path: str | None,
    decisions: list[Mapping[str, Any]] | None,
    track_map: list[Mapping[str, Any]] | None = None,
    api: Any | None = None,
) -> int:
    """Enqueue leftovers when feature flag on. Returns queued leftover count."""
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
    job = AsyncClassifyPatchJob(
        video_id=vid,
        camera_id=camera_id,
        video_path=video_path,
        leftovers=leftovers,
        track_map=mapped,
        api=api,
    )
    with _lock:
        _pending.append(job)
    threading.Thread(
        target=_process_job,
        args=(job,),
        name=f"async-classify-patch-{vid}",
        daemon=True,
    ).start()
    logger.info(
        "async_classify_patch: queued video_id=%s leftovers=%s track_map=%s",
        vid,
        len(leftovers),
        len(mapped),
    )
    return len(leftovers)


def pending_jobs() -> int:
    with _lock:
        return len(_pending)


def _process_job(job: AsyncClassifyPatchJob) -> None:
    """Patch named leftovers via processor enrich API; else stub metric."""
    try:
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
                "async_classify_patch: stub process video_id=%s n=%s "
                "(no named leftover yet; waiting for reclassify fill)",
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
