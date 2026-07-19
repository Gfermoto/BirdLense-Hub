"""RC2 scaffold: async classify leftovers after persist → patch visit (opt-in).

Default off. When enabled, leftover tracks with classify_skip_reason in
{budget, timeout, deferred} are queued after create_video. Full patch path
lands when create_video returns video_species track map + processor enrich API.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Mapping

logger = logging.getLogger(__name__)

SKIP_REASONS = frozenset({"budget", "timeout", "deferred"})


@dataclass
class AsyncClassifyPatchJob:
    video_id: int
    camera_id: str | None
    video_path: str | None
    leftovers: list[dict[str, Any]] = field(default_factory=list)


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
                "decision_kind": row.get("decision_kind"),
            }
        )
    return out


def enqueue_async_classify_patch(
    *,
    app_config: Any,
    video_id: Any,
    camera_id: str | None,
    video_path: str | None,
    decisions: list[Mapping[str, Any]] | None,
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
    job = AsyncClassifyPatchJob(
        video_id=vid,
        camera_id=camera_id,
        video_path=video_path,
        leftovers=leftovers,
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
        "async_classify_patch: queued video_id=%s leftovers=%s",
        vid,
        len(leftovers),
    )
    return len(leftovers)


def pending_jobs() -> int:
    with _lock:
        return len(_pending)


def _process_job(job: AsyncClassifyPatchJob) -> None:
    """Scaffold: log + metric only until enrich PATCH lands."""
    try:
        logger.info(
            "async_classify_patch: stub process video_id=%s n=%s "
            "(waiting for create_video track map + processor enrich patch)",
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
