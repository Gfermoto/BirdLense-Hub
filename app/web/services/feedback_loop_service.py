"""Feedback-learning loop helpers (#397)."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from glob import glob
from pathlib import Path
from typing import Any

from sqlalchemy import func

from models import DetectionFeedbackEvent


logger = logging.getLogger(__name__)


_BACKGROUND_LABELS = {"background", "unknown", "none", "null"}


def _is_background_label(name: str | None) -> bool:
    return str(name or "").strip().lower() in _BACKGROUND_LABELS


def record_feedback_event(
    session,
    *,
    video_species_id: int | None,
    video_id: int | None,
    track_id: int | None,
    from_species_id: int | None,
    to_species_id: int | None,
    from_species_name: str | None,
    to_species_name: str | None,
    trigger_source: str | None,
    apply_scope: str | None,
    reason: str | None,
    detection_provider: str | None,
    confidence: float | None,
    frames_json: str | None,
) -> None:
    action = "delete_as_background" if _is_background_label(to_species_name) else "relabel"
    row = DetectionFeedbackEvent(
        action=action,
        trigger_source=(trigger_source or "").strip() or None,
        apply_scope=(apply_scope or "").strip() or None,
        reason=(reason or "").strip() or None,
        video_species_id=video_species_id,
        video_id=video_id,
        track_id=track_id,
        from_species_id=from_species_id,
        to_species_id=to_species_id,
        from_species_name=(from_species_name or "").strip() or None,
        to_species_name=(to_species_name or "").strip() or None,
        detection_provider=(detection_provider or "").strip() or None,
        confidence=confidence,
        frames_json=frames_json,
    )
    session.add(row)
    session.commit()


def build_feedback_loop_status(session, *, data_dir: str = "app/data") -> dict[str, Any]:
    total = int(session.query(func.count(DetectionFeedbackEvent.id)).scalar() or 0)
    relabel = int(
        session.query(func.count(DetectionFeedbackEvent.id)).filter(DetectionFeedbackEvent.action == "relabel").scalar()
        or 0
    )
    bg = int(
        session.query(func.count(DetectionFeedbackEvent.id))
        .filter(DetectionFeedbackEvent.action == "delete_as_background")
        .scalar()
        or 0
    )
    latest = (
        session.query(DetectionFeedbackEvent)
        .order_by(DetectionFeedbackEvent.created_at.desc(), DetectionFeedbackEvent.id.desc())
        .first()
    )
    status_path = Path(data_dir) / "feedback_exports" / "latest_status.json"
    export_status: dict[str, Any] | None = None
    if status_path.is_file():
        try:
            export_status = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug(
                "Invalid feedback export status JSON: %s",
                status_path,
                exc_info=True,
            )
            export_status = {"status": "invalid_json", "path": str(status_path)}

    return {
        "schema": "feedback_loop_status@v1",
        "events_total": total,
        "events_relabel": relabel,
        "events_delete_as_background": bg,
        "latest_event_at": latest.created_at.isoformat() if latest and latest.created_at else None,
        "latest_export": export_status,
    }


def _safe_label(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return "Unknown"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in raw)[:120] or "Unknown"


def _write_latest_status(output_dir: str, payload: dict[str, Any]) -> None:
    latest_status = Path(output_dir) / "latest_status.json"
    latest_status.parent.mkdir(parents=True, exist_ok=True)
    latest_status.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_feedback_learning_dataset(
    *,
    db_path: str,
    data_dir: str,
    output_dir: str,
    since_hours: int = 24,
    limit: int = 5000,
    dry_run: bool = False,
    export_tag: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=max(int(since_hours), 1))
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        has_table = bool(
            con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='detection_feedback_event'").fetchone()
        )
        if not has_table:
            out_missing = {
                "schema": "feedback_learning_export@v1",
                "status": "missing_table",
                "generated_at_utc": now.isoformat(),
                "db_path": db_path,
                "data_dir": data_dir,
                "since_hours": int(since_hours),
                "dry_run": bool(dry_run),
                "events_total": 0,
            }
            _write_latest_status(
                output_dir,
                {
                    "schema": "feedback_learning_latest_status@v1",
                    "status": "missing_table",
                    "generated_at_utc": now.isoformat(),
                    "events_total": 0,
                    "exported_total": 0,
                    "missing_crop_events": 0,
                    "per_class": {},
                },
            )
            return out_missing

        rows = con.execute(
            """
            SELECT *
            FROM detection_feedback_event
            WHERE created_at >= ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (since.isoformat(), int(limit)),
        ).fetchall()
    finally:
        con.close()

    dataset_train = Path(data_dir) / "dataset" / "train"
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    tag = (str(export_tag or "").strip() or ts).replace("/", "_")
    export_root = Path(output_dir) / f"feedback_export_{tag}"
    hard_root = export_root / "hard_negatives" / "Background"
    pos_root = export_root / "corrected_positives"
    dedup: set[tuple[str, str, str]] = set()
    missing = 0
    copied = 0
    relabel_count = 0
    delete_count = 0
    per_class: dict[str, int] = {}
    exported_items: list[dict[str, Any]] = []

    for row in rows:
        video_id = row["video_id"]
        track_id = row["track_id"]
        if video_id is None or track_id is None:
            missing += 1
            continue
        patt = str(dataset_train / "*" / f"{int(video_id)}_{int(track_id)}_*.jpg")
        matches = glob(patt)
        if not matches:
            missing += 1
            continue
        src = sorted(matches)[-1]
        action = str(row["action"] or "")
        to_name = str(row["to_species_name"] or "")
        if action == "delete_as_background" or _is_background_label(to_name):
            dst_dir = hard_root
            cls = "Background"
            delete_count += 1
        else:
            cls = _safe_label(to_name)
            dst_dir = pos_root / cls
            relabel_count += 1
        key = (action, src, cls)
        if key in dedup:
            continue
        dedup.add(key)
        dst_name = f"{int(row['id'])}_{Path(src).name}"
        dst = dst_dir / dst_name
        if not dry_run:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        copied += 1
        per_class[cls] = per_class.get(cls, 0) + 1
        exported_items.append(
            {
                "event_id": int(row["id"]),
                "action": action,
                "video_species_id": row["video_species_id"],
                "video_id": video_id,
                "track_id": track_id,
                "from_species_name": row["from_species_name"],
                "to_species_name": row["to_species_name"],
                "source_crop": src,
                "export_relpath": str(dst.relative_to(export_root)),
            }
        )

    out = {
        "schema": "feedback_learning_export@v1",
        "generated_at_utc": now.isoformat(),
        "export_tag": tag,
        "db_path": db_path,
        "data_dir": data_dir,
        "since_hours": int(since_hours),
        "events_total": len(rows),
        "exported_total": copied,
        "missing_crop_events": missing,
        "relabel_events_seen": relabel_count,
        "delete_as_background_events_seen": delete_count,
        "per_class": per_class,
        "dry_run": bool(dry_run),
        "export_root": str(export_root),
        "items": exported_items,
    }
    if not dry_run:
        export_root.mkdir(parents=True, exist_ok=True)
        manifest = export_root / "manifest.json"
        manifest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_latest_status(
            output_dir,
            {
                "schema": "feedback_learning_latest_status@v1",
                "status": "ok",
                "generated_at_utc": now.isoformat(),
                "manifest_path": str(manifest),
                "events_total": len(rows),
                "exported_total": copied,
                "missing_crop_events": missing,
                "per_class": per_class,
            },
        )
    else:
        _write_latest_status(
            output_dir,
            {
                "schema": "feedback_learning_latest_status@v1",
                "status": "dry_run_ok",
                "generated_at_utc": now.isoformat(),
                "manifest_path": None,
                "events_total": len(rows),
                "exported_total": copied,
                "missing_crop_events": missing,
                "per_class": per_class,
            },
        )
    return out


def delete_dataset_crops_for_track(*, data_dir: str, video_id: int, track_id: int | None) -> int:
    """Delete dataset crops matching video/track naming convention.

    Returns number of deleted files.
    """
    if track_id is None:
        return 0
    train_root = Path(data_dir) / "dataset" / "train"
    if not train_root.is_dir():
        return 0
    pattern = str(train_root / "*" / f"{int(video_id)}_{int(track_id)}_*.jpg")
    removed = 0
    for fp in glob(pattern):
        try:
            Path(fp).unlink(missing_ok=True)
            removed += 1
        except OSError:
            continue
    return removed
