"""PresenceRecorder product surface (RC1 radical split).

Owns presence / reliability signals: YOLO tracks, generic Bird, persist success.
Does **not** own Hub taxonomy wins — see ``species_recognizer``.
"""

from __future__ import annotations

from typing import Any, Mapping


def summarize_presence(
    *,
    visit_quality: Mapping[str, Any] | None = None,
    video_id: Any = None,
    video_file_ok: bool | None = None,
) -> dict[str, Any]:
    """Compact presence KPI blob for session_summary.presence."""
    vq = visit_quality if isinstance(visit_quality, Mapping) else {}
    return {
        "schema": "presence_recorder@v1",
        "rows": int(vq.get("presence_rows") or 0),
        "persisted_rows": int(vq.get("persisted_rows") or 0),
        "db_persist_success": bool(video_id is not None),
        "video_file_ok": video_file_ok,
    }


def summarize_reliability(
    *,
    video_id: Any = None,
    video_file_ok: bool = False,
    finalize_duration_ms: float | None = None,
    yolo_blind_score: float = 0.0,
    yolo_blind_confirmed: bool = False,
    latency_budget_breaches: list[Any] | None = None,
) -> dict[str, Any]:
    """RC9 reliability namespace — persist/latency, not taxonomy."""
    return {
        "schema": "reliability@v1",
        "db_persist_success": bool(video_id is not None),
        "video_file_ok": bool(video_file_ok),
        "finalize_duration_ms": finalize_duration_ms,
        "yolo_blind_score": round(float(yolo_blind_score or 0.0), 4),
        "yolo_blind_confirmed": bool(yolo_blind_confirmed),
        "latency_budget_breaches": list(latency_budget_breaches or []),
        "post_fusion_persisted": 1 if video_id is not None else 0,
    }


def is_presence_only_row(row: Mapping[str, Any] | None) -> bool:
    from recognition_outcome import OutcomeKind, from_persist_row

    return from_persist_row(row).kind == OutcomeKind.PRESENCE


class PresenceRecorder:
    """Thin service wrapper — presence/reliability SLOs, not taxonomy."""

    name = "presence_recorder"

    def summarize(
        self,
        *,
        visit_quality: Mapping[str, Any] | None = None,
        video_id: Any = None,
        video_file_ok: bool | None = None,
    ) -> dict[str, Any]:
        return summarize_presence(
            visit_quality=visit_quality,
            video_id=video_id,
            video_file_ok=video_file_ok,
        )

    def reliability(
        self,
        *,
        video_id: Any = None,
        video_file_ok: bool = False,
        finalize_duration_ms: float | None = None,
        yolo_blind_score: float = 0.0,
        yolo_blind_confirmed: bool = False,
        latency_budget_breaches: list[Any] | None = None,
    ) -> dict[str, Any]:
        return summarize_reliability(
            video_id=video_id,
            video_file_ok=video_file_ok,
            finalize_duration_ms=finalize_duration_ms,
            yolo_blind_score=yolo_blind_score,
            yolo_blind_confirmed=yolo_blind_confirmed,
            latency_budget_breaches=latency_budget_breaches,
        )

    def is_presence_only(self, row: Mapping[str, Any] | None) -> bool:
        return is_presence_only_row(row)
