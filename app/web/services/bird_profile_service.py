"""Bird Profile CRUD, linking, and expert semantic-review workflow."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from models import ActiveLearningCase, BirdProfile, VideoSpecies, db
from services.reid_auto_link_service import auto_link_hook, merge_bird_profiles as _merge_bird_profiles


SEMANTIC_REVIEW_STATUS = "semantic_review_required"
SEMANTIC_REVIEW_REASON = "semantic_review_required"


def _parse_payload(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(str(raw or "{}"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _append_semantic_history(case: ActiveLearningCase, *, source: str, note: str | None) -> None:
    payload = _parse_payload(case.payload_json)
    history = payload.get("semantic_review_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "source": str(source or "unknown"),
            "note": (str(note).strip()[:500] or None) if note is not None else None,
        }
    )
    payload["semantic_review_history"] = history[-30:]
    case.payload_json = json.dumps(payload, ensure_ascii=False)


def list_bird_profiles(*, query: str | None = None, species_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit or 20), 100))
    q = db.session.query(BirdProfile).order_by(BirdProfile.created_at.desc())
    if species_id is not None:
        q = q.filter(BirdProfile.species_id == int(species_id))
    needle = (query or "").strip()
    if needle:
        q = q.filter(BirdProfile.display_name.ilike(f"%{needle}%"))
    rows = q.limit(lim).all()
    return [
        {
            "id": int(row.id),
            "display_name": row.display_name,
            "species_id": row.species_id,
            "avatar_url": row.avatar_url,
            "status": row.status,
            "created_at": row.created_at.astimezone(timezone.utc).isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def create_bird_profile(*, display_name: str, species_id: int | None = None, avatar_url: str | None = None, status: str | None = None) -> dict[str, Any]:
    name = str(display_name or "").strip()
    if not name:
        raise ValueError("display_name is required")
    row = BirdProfile(
        display_name=name[:96],
        species_id=int(species_id) if species_id is not None else None,
        avatar_url=(str(avatar_url).strip()[:512] or None) if avatar_url is not None else None,
        status=(str(status).strip()[:32] or "active"),
    )
    db.session.add(row)
    db.session.commit()
    return {
        "id": int(row.id),
        "display_name": row.display_name,
        "species_id": row.species_id,
        "avatar_url": row.avatar_url,
        "status": row.status,
    }


def update_bird_profile(*, profile_id: int, display_name: str | None = None, avatar_url: str | None = None, status: str | None = None) -> dict[str, Any]:
    row = db.session.get(BirdProfile, int(profile_id))
    if row is None:
        raise LookupError("profile not found")
    if display_name is not None:
        name = str(display_name).strip()
        if not name:
            raise ValueError("display_name cannot be empty")
        row.display_name = name[:96]
    if avatar_url is not None:
        row.avatar_url = str(avatar_url).strip()[:512] or None
    if status is not None:
        row.status = str(status).strip()[:32] or "active"
    db.session.flush()
    if display_name is not None:
        db.session.query(VideoSpecies).filter(VideoSpecies.bird_profile_id == row.id).update(
            {"individual_nickname": row.display_name},
            synchronize_session=False,
        )
    db.session.commit()
    return {
        "id": int(row.id),
        "display_name": row.display_name,
        "species_id": row.species_id,
        "avatar_url": row.avatar_url,
        "status": row.status,
    }


def assign_profile_to_detection(*, detection_id: int, bird_profile_id: int) -> dict[str, Any]:
    vs = db.session.get(VideoSpecies, int(detection_id))
    if vs is None:
        raise LookupError("detection not found")
    profile = db.session.get(BirdProfile, int(bird_profile_id))
    if profile is None:
        raise LookupError("profile not found")
    # Correction propagation: keep one identity across all detections inside the same video session.
    targets = db.session.query(VideoSpecies).filter(VideoSpecies.video_id == vs.video_id).all()
    for row in targets:
        row.bird_profile_id = profile.id
        row.individual_nickname = profile.display_name
    db.session.commit()
    return {
        "detection_id": int(vs.id),
        "video_id": int(vs.video_id),
        "bird_profile_id": int(profile.id),
        "updated_count": len(targets),
        "auto_link_hook": auto_link_profile_candidate(video_species_id=vs.id),
    }


def set_detection_semantic_review(*, detection_id: int, required: bool, note: str | None = None, source: str = "video_details") -> dict[str, Any]:
    vs = db.session.get(VideoSpecies, int(detection_id))
    if vs is None:
        raise LookupError("detection not found")
    if required:
        vs.classifier_needs_review = True
        vs.review_reason = SEMANTIC_REVIEW_REASON
        case = (
            db.session.query(ActiveLearningCase)
            .filter(
                ActiveLearningCase.video_species_id == vs.id,
                ActiveLearningCase.reason_code == SEMANTIC_REVIEW_REASON,
            )
            .one_or_none()
        )
        if case is None:
            case = ActiveLearningCase(
                video_id=vs.video_id,
                video_species_id=vs.id,
                reason_code=SEMANTIC_REVIEW_REASON,
                confidence=vs.confidence,
                status=SEMANTIC_REVIEW_STATUS,
            )
            db.session.add(case)
        case.status = SEMANTIC_REVIEW_STATUS
        case.updated_at = datetime.now(timezone.utc)
        _append_semantic_history(case, source=source, note=note)
    else:
        vs.classifier_needs_review = False
        if vs.review_reason == SEMANTIC_REVIEW_REASON:
            vs.review_reason = None
    db.session.commit()
    return {
        "detection_id": int(vs.id),
        "required": bool(required),
        "review_reason": vs.review_reason,
    }


def auto_link_profile_candidate(*, video_species_id: int) -> dict[str, Any]:
    return auto_link_hook(video_species_id=int(video_species_id))


def merge_bird_profiles(*, target_profile_id: int, source_profile_id: int) -> dict[str, Any]:
    return _merge_bird_profiles(
        target_profile_id=int(target_profile_id),
        source_profile_id=int(source_profile_id),
    )

