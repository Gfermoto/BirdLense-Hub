"""Track-first product contract: persisted video visits require YOLO bbox+track.

North star (processor/README): trigger → YOLO+ByteTrack → persist with frames[].
No synthetic video rows without bbox; no ingest after frame strip.
"""

from __future__ import annotations

from typing import Any

_BBOX_PROVIDERS = frozenset(
    {
        "yolo",
        "opencv",
        "detector",
        "binary",
        "motion_detector",
        "or_motion",
    }
)


def is_valid_norm_bbox(bbox: Any) -> bool:
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return False
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
    except (TypeError, ValueError):
        return False
    if not (x2 > x1 and y2 > y1):
        return False
    low, high = -0.05, 1.05
    return all(low <= v <= high for v in (x1, y1, x2, y2))


def valid_track_frames(frames: Any) -> list[dict[str, Any]]:
    if not isinstance(frames, list):
        return []
    out: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        if is_valid_norm_bbox(frame.get("bbox")):
            out.append(frame)
    return out


def row_requires_bbox(row: dict[str, Any]) -> bool:
    source = str((row or {}).get("source") or "").strip().lower()
    if source != "video":
        return False
    provider = str((row or {}).get("detection_provider") or "").strip().lower()
    if provider in _BBOX_PROVIDERS:
        return True
    return bool((row or {}).get("yolo_track_present"))


def apply_track_first_persist_gate(
    rows: list[dict[str, Any]] | None,
    *,
    enabled: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Drop video-source rows that cannot satisfy bbox+track ingest contract."""
    if not enabled:
        return list(rows or []), []
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows or []:
        if not row_requires_bbox(row):
            kept.append(row)
            continue
        valid_frames = valid_track_frames(row.get("frames"))
        if not valid_frames:
            rejected.append(
                {
                    "species_name": row.get("species_name") or row.get("species"),
                    "detection_provider": row.get("detection_provider"),
                    "reject_reason_code": "track_first_missing_bbox",
                    "decision_reason": "rejected_track_first_no_bbox",
                    "decision_kind": "rejected",
                }
            )
            continue
        if len(valid_frames) != len(row.get("frames") or []):
            row = dict(row)
            row["frames"] = valid_frames
        kept.append(row)
    return kept, rejected


def count_ingestible_track_rows(rows: list[dict[str, Any]] | None) -> int:
    return sum(
        1
        for row in rows or []
        if row_requires_bbox(row) and valid_track_frames(row.get("frames"))
    )


def has_ingestible_track_rows(rows: list[dict[str, Any]] | None) -> bool:
    return count_ingestible_track_rows(rows) > 0


def _row_accepted_for_persist(row: dict[str, Any]) -> bool:
    kind = str(row.get("decision_kind") or "").strip().lower()
    if kind in {"review_only_generic", "review_only", "rejected"}:
        return False
    if row.get("accepted") is False:
        return False
    return True


def has_accepted_ingestible_track_rows(rows: list[dict[str, Any]] | None) -> bool:
    """Rows that can actually be persisted (accepted visit + valid bbox frames)."""
    return any(
        _row_accepted_for_persist(row) and row_requires_bbox(row) and valid_track_frames(row.get("frames"))
        for row in (rows or [])
    )
