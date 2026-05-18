"""Hard-example miner and labelling export helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from models import ActiveLearningCase, Species, Video, VideoSpecies, db
from util import data_dir

_REASON_BLIND = "blind_score_high"
_REASON_FALLBACK = "fallback_ratio_high"
_REASON_LOWCONF = "confidence_borderline"
_ALLOWED_STATUS = {"pending", "approved", "rejected"}
_ALLOWED_FEEDBACK_ACTION = {"confirm_behavior", "reject_box", "tag_species"}


def _parse_payload(raw: str | None) -> dict[str, Any]:
    try:
        p = json.loads(str(raw or "{}"))
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}


def _parse_json_any(raw: str | None) -> Any:
    try:
        return json.loads(str(raw or "null"))
    except Exception:
        return None


def _next_dataset_version(base_dir: Path) -> str:
    versions = []
    for p in base_dir.glob("v*"):
        if p.is_dir():
            try:
                versions.append(int(str(p.name).lstrip("v")))
            except ValueError:
                continue
    n = (max(versions) + 1) if versions else 1
    return f"v{n}"


def _insert_case(
    *,
    video_id: int | None,
    video_species_id: int | None,
    camera_id: str | None,
    reason_code: str,
    confidence: float | None,
    blind_score: float | None,
    fallback_ratio: float | None,
    payload: dict[str, Any],
) -> bool:
    if video_species_id is not None:
        exists = db.session.execute(
            text(
                """
                SELECT id
                FROM active_learning_case
                WHERE video_species_id = :video_species_id AND reason_code = :reason_code
                LIMIT 1
                """
            ),
            {"video_species_id": int(video_species_id), "reason_code": reason_code},
        ).first()
        if exists:
            return False
    runtime_id = payload.get("runtime_id") if isinstance(payload, dict) else None
    if runtime_id is not None:
        exists_runtime = db.session.execute(
            text(
                """
                SELECT id
                FROM active_learning_case
                WHERE reason_code = :reason_code
                  AND json_extract(payload_json, '$.runtime_id') = :runtime_id
                LIMIT 1
                """
            ),
            {"reason_code": reason_code, "runtime_id": int(runtime_id)},
        ).first()
        if exists_runtime:
            return False
    row = ActiveLearningCase(
        video_id=video_id,
        video_species_id=video_species_id,
        camera_id=(str(camera_id).strip() or None) if camera_id is not None else None,
        reason_code=reason_code,
        confidence=confidence,
        blind_score=blind_score,
        fallback_ratio=fallback_ratio,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.session.add(row)
    return True


def mine_hard_examples(
    *,
    lookback_hours: int = 72,
    max_rows: int = 400,
    blind_score_threshold: float = 0.5,
    fallback_ratio_threshold: float = 0.35,
    conf_min: float = 0.20,
    conf_max: float = 0.35,
) -> dict[str, int]:
    window_h = max(1, min(int(lookback_hours), 24 * 30))
    lim = max(1, min(int(max_rows), 5000))
    created = 0
    skipped = 0

    runtime_rows = db.session.execute(
        text(
            """
            SELECT id, created_at, camera_id, payload_json
            FROM session_runtime_metrics
            WHERE datetime(created_at) >= datetime('now', :window)
            ORDER BY id DESC
            LIMIT :lim
            """
        ),
        {"window": f"-{window_h} hours", "lim": lim},
    ).mappings()
    for row in runtime_rows:
        payload = _parse_payload(row.get("payload_json"))
        blind_score = payload.get("yolo_blind_score")
        try:
            blind_score_f = float(blind_score) if blind_score is not None else None
        except (TypeError, ValueError):
            blind_score_f = None
        yolo = int(payload.get("yolo_frames_ran") or 0)
        fr_only = int(payload.get("session_extended_by_frigate_only") or 0)
        fallback_ratio = (float(fr_only) / float(yolo)) if yolo > 0 else None
        if blind_score_f is not None and blind_score_f >= blind_score_threshold:
            if _insert_case(
                video_id=None,
                video_species_id=None,
                camera_id=row.get("camera_id"),
                reason_code=_REASON_BLIND,
                confidence=None,
                blind_score=blind_score_f,
                fallback_ratio=fallback_ratio,
                payload={
                    "runtime_id": int(row["id"]),
                    "created_at": str(row.get("created_at")),
                    "blind_score": blind_score_f,
                    "fallback_ratio": fallback_ratio,
                },
            ):
                created += 1
            else:
                skipped += 1
        if fallback_ratio is not None and fallback_ratio >= fallback_ratio_threshold:
            if _insert_case(
                video_id=None,
                video_species_id=None,
                camera_id=row.get("camera_id"),
                reason_code=_REASON_FALLBACK,
                confidence=None,
                blind_score=blind_score_f,
                fallback_ratio=fallback_ratio,
                payload={
                    "runtime_id": int(row["id"]),
                    "created_at": str(row.get("created_at")),
                    "blind_score": blind_score_f,
                    "fallback_ratio": fallback_ratio,
                },
            ):
                created += 1
            else:
                skipped += 1

    vs_rows = db.session.execute(
        text(
            """
            SELECT
              vs.id AS video_species_id,
              vs.video_id,
              vs.confidence,
              vs.track_id,
              vs.frames,
              COALESCE(vs.detection_provider, 'legacy') AS detection_provider
            FROM video_species vs
            JOIN video v ON v.id = vs.video_id
            WHERE datetime(v.start_time) >= datetime('now', :window)
              AND vs.source = 'video'
              AND vs.confidence >= :conf_min
              AND vs.confidence <= :conf_max
            ORDER BY vs.id DESC
            LIMIT :lim
            """
        ),
        {"window": f"-{window_h} hours", "conf_min": conf_min, "conf_max": conf_max, "lim": lim},
    ).mappings()
    for row in vs_rows:
        if _insert_case(
            video_id=int(row["video_id"]),
            video_species_id=int(row["video_species_id"]),
            camera_id=None,
            reason_code=_REASON_LOWCONF,
            confidence=float(row.get("confidence") or 0.0),
            blind_score=None,
            fallback_ratio=None,
            payload={
                "track_id": row.get("track_id"),
                "frames": _parse_payload(row.get("frames")) if row.get("frames") else None,
                "detection_provider": row.get("detection_provider"),
            },
        ):
            created += 1
        else:
            skipped += 1

    db.session.commit()
    return {"created": created, "skipped": skipped}


def list_cases(*, status: str | None = None, limit: int = 100) -> dict[str, Any]:
    lim = max(1, min(int(limit), 500))
    q = (
        db.session.query(ActiveLearningCase, VideoSpecies, Species, Video)
        .outerjoin(VideoSpecies, ActiveLearningCase.video_species_id == VideoSpecies.id)
        .outerjoin(Species, VideoSpecies.species_id == Species.id)
        .outerjoin(Video, ActiveLearningCase.video_id == Video.id)
        .order_by(ActiveLearningCase.created_at.desc())
    )
    if status and status in _ALLOWED_STATUS:
        q = q.filter(ActiveLearningCase.status == status)
    rows = q.limit(lim).all()
    items = []
    for case, vs, species, video in rows:
        items.append(
            {
                "id": int(case.id),
                "created_at": case.created_at.astimezone(timezone.utc).isoformat() if case.created_at else None,
                "updated_at": case.updated_at.astimezone(timezone.utc).isoformat() if case.updated_at else None,
                "status": case.status,
                "reason_code": case.reason_code,
                "camera_id": case.camera_id,
                "video_id": case.video_id,
                "video_species_id": case.video_species_id,
                "species_name": species.name if species else None,
                "video_path": video.video_path if video else None,
                "confidence": case.confidence,
                "blind_score": case.blind_score,
                "fallback_ratio": case.fallback_ratio,
                "payload": _parse_payload(case.payload_json),
                "behavior_label": getattr(video, "behavior_label", None) if video else None,
                "behavior_confidence": getattr(video, "behavior_confidence", None) if video else None,
                "behavior_shadow_label": getattr(video, "behavior_shadow_label", None) if video else None,
                "behavior_shadow_confidence": getattr(video, "behavior_shadow_confidence", None) if video else None,
            }
        )
    return {"items": items, "count": len(items)}


def patch_case(*, case_id: int, status: str, reason_note: str | None = None) -> dict[str, Any]:
    norm_status = str(status or "").strip().lower()
    if norm_status not in _ALLOWED_STATUS:
        raise ValueError("status must be pending|approved|rejected")
    row = db.session.get(ActiveLearningCase, int(case_id))
    if row is None:
        raise LookupError("case not found")
    row.status = norm_status
    row.updated_at = datetime.now(timezone.utc)
    payload = _parse_payload(row.payload_json)
    if reason_note:
        payload["review_note"] = str(reason_note).strip()[:500]
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    db.session.commit()
    return {"id": int(row.id), "status": row.status}


def apply_case_feedback(
    *,
    case_id: int,
    action: str,
    behavior_tag: str | None = None,
    species_tag: str | None = None,
) -> dict[str, Any]:
    action_norm = str(action or "").strip().lower()
    if action_norm not in _ALLOWED_FEEDBACK_ACTION:
        raise ValueError("action must be confirm_behavior|reject_box|tag_species")
    row = db.session.get(ActiveLearningCase, int(case_id))
    if row is None:
        raise LookupError("case not found")
    payload = _parse_payload(row.payload_json)
    payload["last_feedback_action"] = action_norm

    if action_norm == "confirm_behavior":
        label = (str(behavior_tag or "").strip().lower() or payload.get("behavior_tag") or "").strip()
        if not label:
            raise ValueError("behavior_tag is required for confirm_behavior")
        payload["behavior_tag"] = label
        if row.video_id is not None:
            video = db.session.get(Video, int(row.video_id))
            if video is not None:
                video.behavior_label = label[:32]
                video.behavior_confidence = 1.0
        row.status = "approved"

    elif action_norm == "reject_box":
        payload["localization_status"] = "rejected"
        if row.video_species_id is not None:
            vs = db.session.get(VideoSpecies, int(row.video_species_id))
            if vs is not None:
                vs.frames = None
                vs.classifier_needs_review = True
                vs.review_reason = "bbox_rejected"
        row.status = "rejected"

    elif action_norm == "tag_species":
        tag = str(species_tag or "").strip()
        if not tag:
            raise ValueError("species_tag is required for tag_species")
        payload["species_tag"] = tag
        if row.video_species_id is not None:
            sp = db.session.query(Species).filter(Species.name == tag).one_or_none()
            vs = db.session.get(VideoSpecies, int(row.video_species_id))
            if sp is not None and vs is not None:
                vs.species_id = int(sp.id)
        row.status = "approved"

    row.updated_at = datetime.now(timezone.utc)
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    db.session.commit()
    return {"id": int(row.id), "status": row.status, "action": action_norm}


def export_cases(*, fmt: str = "yolo", status: str = "approved", version: str | None = None) -> dict[str, Any]:
    fmt_norm = str(fmt or "yolo").strip().lower()
    if fmt_norm not in {"yolo", "coco"}:
        raise ValueError("format must be yolo|coco")
    status_norm = str(status or "approved").strip().lower()
    if status_norm not in _ALLOWED_STATUS:
        raise ValueError("status must be pending|approved|rejected")

    rows = (
        db.session.query(ActiveLearningCase, VideoSpecies, Species)
        .outerjoin(VideoSpecies, ActiveLearningCase.video_species_id == VideoSpecies.id)
        .outerjoin(Species, VideoSpecies.species_id == Species.id)
        .filter(ActiveLearningCase.status == status_norm)
        .order_by(ActiveLearningCase.created_at.desc())
        .all()
    )
    base = Path(data_dir()) / "datasets"
    base.mkdir(parents=True, exist_ok=True)
    ver = version or _next_dataset_version(base)
    dst = base / ver
    dst.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    if fmt_norm == "yolo":
        labels_dir = dst / "labels"
        labels_dir.mkdir(parents=True, exist_ok=True)
        classes: list[str] = []
        class_to_id: dict[str, int] = {}
        written = 0
        for case, vs, species in rows:
            if vs is None or species is None:
                continue
            cls_name = species.name
            if cls_name not in class_to_id:
                class_to_id[cls_name] = len(classes)
                classes.append(cls_name)
            cls_id = class_to_id[cls_name]
            frames = _parse_json_any(vs.frames)
            bbox = None
            if isinstance(frames, list) and frames:
                f0 = frames[0]
                if isinstance(f0, dict):
                    b = f0.get("bbox")
                    if isinstance(b, list) and len(b) == 4:
                        bbox = [float(x) for x in b]
            if bbox is None:
                bbox = [0.25, 0.25, 0.75, 0.75]
            x1, y1, x2, y2 = bbox
            cx = max(0.0, min(1.0, (x1 + x2) / 2.0))
            cy = max(0.0, min(1.0, (y1 + y2) / 2.0))
            w = max(0.0, min(1.0, x2 - x1))
            h = max(0.0, min(1.0, y2 - y1))
            label_name = f"case_{case.id}.txt"
            (labels_dir / label_name).write_text(
                f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n",
                encoding="utf-8",
            )
            written += 1
        (dst / "classes.txt").write_text("\n".join(classes), encoding="utf-8")
        manifest = {
            "format": "yolo",
            "version": ver,
            "created_at": now,
            "status_filter": status_norm,
            "labels_count": written,
            "classes_count": len(classes),
        }
        (dst / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"version": ver, "format": "yolo", "labels_count": written, "path": str(dst)}

    categories: dict[str, int] = {}
    images = []
    annotations = []
    ann_id = 1
    for case, vs, species in rows:
        if vs is None or species is None:
            continue
        cls_name = species.name
        if cls_name not in categories:
            categories[cls_name] = len(categories) + 1
        cat_id = categories[cls_name]
        image_id = int(case.id)
        images.append({"id": image_id, "file_name": f"case_{case.id}.jpg", "width": 1, "height": 1})
        frames = _parse_json_any(vs.frames)
        bbox = [0.25, 0.25, 0.5, 0.5]
        if isinstance(frames, list) and frames and isinstance(frames[0], dict):
            b = frames[0].get("bbox")
            if isinstance(b, list) and len(b) == 4:
                x1, y1, x2, y2 = [float(x) for x in b]
                bbox = [x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)]
        annotations.append(
            {
                "id": ann_id,
                "image_id": image_id,
                "category_id": cat_id,
                "bbox": bbox,
                "area": float(bbox[2] * bbox[3]),
                "iscrowd": 0,
            }
        )
        ann_id += 1
    coco = {
        "info": {"description": "BirdLense Active Learning export", "version": ver, "date_created": now},
        "images": images,
        "annotations": annotations,
        "categories": [{"id": cid, "name": name} for name, cid in categories.items()],
    }
    (dst / "annotations.coco.json").write_text(json.dumps(coco, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"version": ver, "format": "coco", "annotations_count": len(annotations), "path": str(dst)}
