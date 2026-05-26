"""Expert review queue: ReID duplicates, low confidence, semantic conflicts (SOTA-13)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app_config.app_config import app_config
from models import ExpertReviewQueue, Species, Video, VideoSpecies, db
from services.bird_profile_service import assign_profile_to_detection, merge_bird_profiles
from services.reid_track_cluster_service import (
    cosine_similarity,
    load_cluster_config,
    load_track_embeddings,
    reid_gallery_enabled,
    cluster_track_embeddings,
)


def expert_queue_enabled() -> bool:
    if not reid_gallery_enabled():
        return False
    return _cfg_bool("processor.reid_expert_queue_enabled", False)


def _cfg_bool(key: str, default: bool) -> bool:
    raw = app_config.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _parse_payload(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(str(raw or "{}"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def sync_duplicate_tasks(*, video_id: int | None = None, limit: int = 200) -> int:
    """Enqueue duplicate-candidate tasks from embedding clusters (idempotent per cluster_key)."""
    if not expert_queue_enabled():
        return 0
    rows = load_track_embeddings(video_id=video_id, limit=limit)
    clusters = cluster_track_embeddings(rows)
    cfg = load_cluster_config()
    dup_low = float(cfg["duplicate_low"])
    row_by_id = {r.video_species_id: r for r in rows}
    created = 0
    for cl in clusters:
        if len(cl.member_video_species_ids) < 2:
            continue
        if cl.centroid_similarity < dup_low:
            continue
        cluster_key = f"dup:{cl.cluster_id}"
        exists = (
            db.session.query(ExpertReviewQueue.id)
            .filter(
                ExpertReviewQueue.cluster_key == cluster_key,
                ExpertReviewQueue.status == "pending",
            )
            .first()
        )
        if exists:
            continue
        ids = cl.member_video_species_ids[:2]
        a, b = ids[0], ids[1]
        ra, rb = row_by_id.get(a), row_by_id.get(b)
        sim = cosine_similarity(ra.embedding, rb.embedding) if ra and rb else cl.centroid_similarity
        task = ExpertReviewQueue(
            task_type="duplicate_candidate",
            status="pending",
            video_species_id=a,
            related_video_species_id=b,
            cluster_key=cluster_key,
            similarity=float(sim),
            species_id=cl.species_id,
            payload_json=json.dumps(
                {
                    "member_video_species_ids": cl.member_video_species_ids,
                    "min_pairwise_similarity": cl.centroid_similarity,
                },
                ensure_ascii=False,
            ),
        )
        db.session.add(task)
        created += 1
    if created:
        db.session.commit()
    return created


def list_expert_queue(
    *,
    status: str = "pending",
    limit: int = 50,
    sync: bool = True,
) -> dict[str, Any]:
    if not expert_queue_enabled():
        return {"enabled": False, "items": [], "message": "expert_queue_disabled"}
    if sync:
        sync_duplicate_tasks(limit=300)
    lim = max(1, min(int(limit or 50), 200))
    status_norm = str(status or "pending").strip().lower() or "pending"
    q = (
        db.session.query(ExpertReviewQueue, VideoSpecies, Species, Video)
        .outerjoin(VideoSpecies, ExpertReviewQueue.video_species_id == VideoSpecies.id)
        .outerjoin(Species, VideoSpecies.species_id == Species.id)
        .outerjoin(Video, VideoSpecies.video_id == Video.id)
        .filter(ExpertReviewQueue.status == status_norm)
        .order_by(ExpertReviewQueue.created_at.desc())
        .limit(lim)
    )
    items = []
    for row, vs, sp, vid in q.all():
        items.append(
            {
                "id": int(row.id),
                "task_type": row.task_type,
                "status": row.status,
                "video_species_id": row.video_species_id,
                "related_video_species_id": row.related_video_species_id,
                "cluster_key": row.cluster_key,
                "similarity": round(float(row.similarity), 4) if row.similarity is not None else None,
                "species_id": row.species_id,
                "species_name": sp.name if sp else None,
                "video_id": vs.video_id if vs else None,
                "video_start_time": vid.start_time.astimezone(timezone.utc).isoformat() if vid and vid.start_time else None,
                "payload": _parse_payload(row.payload_json),
                "created_at": row.created_at.astimezone(timezone.utc).isoformat() if row.created_at else None,
            }
        )
    return {"enabled": True, "items": items, "count": len(items)}


def resolve_expert_task(
    *,
    task_id: int,
    action: str,
    species_id: int | None = None,
    target_profile_id: int | None = None,
    source_profile_id: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if not expert_queue_enabled():
        raise ValueError("expert_queue_disabled")
    row = db.session.get(ExpertReviewQueue, int(task_id))
    if row is None:
        raise LookupError("task not found")
    if row.status != "pending":
        raise ValueError("task already resolved")
    act = str(action or "").strip().lower()
    result: dict[str, Any] = {"task_id": int(task_id), "action": act}

    if act == "dismiss":
        row.status = "dismissed"
    elif act == "confirm_species":
        if species_id is None or row.video_species_id is None:
            raise ValueError("species_id required")
        vs = db.session.get(VideoSpecies, int(row.video_species_id))
        sp = db.session.get(Species, int(species_id))
        if vs is None or sp is None:
            raise LookupError("detection or species not found")
        vs.species_id = int(species_id)
        vs.manually_corrected = True
        vs.classifier_needs_review = False
        vs.review_reason = None
        row.status = "resolved"
        result["video_species_id"] = int(row.video_species_id)
        result["species_name"] = sp.name
    elif act == "merge_profiles":
        if target_profile_id is None or source_profile_id is None:
            raise ValueError("target_profile_id and source_profile_id required")
        payload = merge_bird_profiles(
            target_profile_id=int(target_profile_id),
            source_profile_id=int(source_profile_id),
        )
        row.status = "resolved"
        result["merge"] = payload
    elif act == "merge_tracks":
        if row.video_species_id is None or row.related_video_species_id is None:
            raise ValueError("merge_tracks requires both detections")
        if target_profile_id is not None:
            assign_profile_to_detection(
                detection_id=int(row.video_species_id),
                bird_profile_id=int(target_profile_id),
            )
            assign_profile_to_detection(
                detection_id=int(row.related_video_species_id),
                bird_profile_id=int(target_profile_id),
            )
        row.status = "resolved"
        result["linked_video_species_ids"] = [
            int(row.video_species_id),
            int(row.related_video_species_id),
        ]
    else:
        raise ValueError(f"unsupported action: {act}")

    row.resolved_at = datetime.now(timezone.utc)
    if note:
        payload = _parse_payload(row.payload_json)
        payload["resolve_note"] = str(note)[:500]
        row.payload_json = json.dumps(payload, ensure_ascii=False)
    db.session.commit()
    return result


def export_expert_verified_dataset(*, limit: int = 500) -> dict[str, Any]:
    """Write resolved expert tasks to datasets/expert_verified/ for active learning."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    out_dir = repo_root / "datasets" / "expert_verified"
    out_dir.mkdir(parents=True, exist_ok=True)
    lim = max(1, min(int(limit or 500), 5000))
    rows = (
        db.session.query(ExpertReviewQueue)
        .filter(ExpertReviewQueue.status.in_(("resolved", "dismissed")))
        .order_by(ExpertReviewQueue.resolved_at.desc())
        .limit(lim)
        .all()
    )
    manifest = []
    for row in rows:
        manifest.append(
            {
                "task_id": int(row.id),
                "task_type": row.task_type,
                "status": row.status,
                "video_species_id": row.video_species_id,
                "related_video_species_id": row.related_video_species_id,
                "similarity": row.similarity,
                "species_id": row.species_id,
                "payload": _parse_payload(row.payload_json),
                "resolved_at": row.resolved_at.astimezone(timezone.utc).isoformat() if row.resolved_at else None,
            }
        )
    out_path = out_dir / "expert_verified_manifest.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for entry in manifest:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"path": str(out_path), "count": len(manifest)}
