"""Auto-link bird profiles via ReID embedding cosine similarity."""

from __future__ import annotations

import json
import math
from datetime import timezone
from typing import Any

from sqlalchemy import text

from app_config.app_config import app_config
from models import BirdProfile, ReidTrainingPair, VideoSpecies, db


def _as_bool(val: Any, default: bool) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        s = val.strip().lower()
        if s in {"1", "true", "yes", "on"}:
            return True
        if s in {"0", "false", "no", "off"}:
            return False
    return default


def _as_float(val: Any, default: float) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def load_auto_link_config() -> dict[str, Any]:
    return {
        "enabled": _as_bool(app_config.get("processor.reid_auto_link_enabled"), True),
        "threshold_high": _as_float(app_config.get("processor.reid_auto_link_threshold_high"), 0.95),
        "threshold_low": _as_float(app_config.get("processor.reid_auto_link_threshold_low"), 0.75),
        "max_candidates": int(_as_float(app_config.get("processor.reid_auto_link_max_candidates"), 8)),
    }


def _parse_embedding(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    try:
        vals = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(vals, list):
        return None
    try:
        out = [float(v) for v in vals]
    except (TypeError, ValueError):
        return None
    return out if out else None


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0.0 or nb <= 0.0:
        return -1.0
    return dot / (na * nb)


def _mean_normalized(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    dim = len(vectors[0])
    if dim <= 0:
        return None
    acc = [0.0] * dim
    n = 0
    for vec in vectors:
        if len(vec) != dim:
            continue
        for i, v in enumerate(vec):
            acc[i] += v
        n += 1
    if n <= 0:
        return None
    mean = [v / n for v in acc]
    norm = math.sqrt(sum(v * v for v in mean))
    if norm <= 0.0:
        return mean
    return [v / norm for v in mean]


def _reid_table_ready() -> bool:
    return bool(
        db.session.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reid_embedding'")).scalar()
    )


def _fetch_anchor_embedding(*, video_species_id: int) -> list[float] | None:
    row = (
        db.session.execute(
            text("SELECT embedding_json FROM reid_embedding WHERE video_species_id = :vsid ORDER BY id DESC LIMIT 1"),
            {"vsid": int(video_species_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    return _parse_embedding(row.get("embedding_json"))


def _profile_centroids(
    *, exclude_profile_id: int | None = None, species_id: int | None = None
) -> dict[int, list[float]]:
    if not _reid_table_ready():
        return {}
    params: dict[str, Any] = {}
    filters = ["vs.bird_profile_id IS NOT NULL"]
    if exclude_profile_id is not None and int(exclude_profile_id) > 0:
        filters.append("vs.bird_profile_id != :exclude_id")
        params["exclude_id"] = int(exclude_profile_id)
    if species_id is not None:
        filters.append("vs.species_id = :species_id")
        params["species_id"] = int(species_id)
    where = " AND ".join(filters)
    rows = (
        db.session.execute(
            text(
                f"SELECT vs.bird_profile_id AS profile_id, re.embedding_json AS embedding_json "  # nosec B608
                f"FROM reid_embedding re "
                f"INNER JOIN video_species vs ON vs.id = re.video_species_id "
                f"WHERE {where} "
                f"ORDER BY re.id DESC LIMIT 5000"
            ),
            params,
        )
        .mappings()
        .all()
    )
    by_profile: dict[int, list[list[float]]] = {}
    for row in rows:
        pid = row.get("profile_id")
        emb = _parse_embedding(row.get("embedding_json"))
        if pid is None or emb is None:
            continue
        by_profile.setdefault(int(pid), []).append(emb)
    out: dict[int, list[float]] = {}
    for pid, vecs in by_profile.items():
        centroid = _mean_normalized(vecs)
        if centroid is not None:
            out[pid] = centroid
    return out


def _tier_for_score(*, score: float, cfg: dict[str, Any]) -> str | None:
    if score >= float(cfg["threshold_high"]):
        return "auto"
    if score >= float(cfg["threshold_low"]):
        return "suggest"
    return None


def suggest_profile_links(
    *,
    profile_id: int | None = None,
    video_species_id: int | None = None,
    species_id: int | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    cfg = load_auto_link_config()
    lim = max(1, min(int(limit or cfg["max_candidates"]), 20))
    base: dict[str, Any] = {
        "schema": "bird_profile_suggest_links@v1",
        "available": False,
        "thresholds": {
            "high": float(cfg["threshold_high"]),
            "low": float(cfg["threshold_low"]),
        },
        "candidates": [],
    }
    if not cfg["enabled"]:
        base["message"] = "reid_auto_link_disabled"
        return base
    if not _reid_table_ready():
        base["message"] = "reid_embedding_table_missing"
        return base

    anchor: list[float] | None = None
    resolved_species_id = species_id
    if video_species_id is not None:
        vs = db.session.get(VideoSpecies, int(video_species_id))
        if vs is None:
            raise LookupError("detection not found")
        anchor = _fetch_anchor_embedding(video_species_id=int(vs.id))
        if resolved_species_id is None:
            resolved_species_id = vs.species_id
    elif profile_id is not None and int(profile_id) > 0:
        rows = (
            db.session.query(VideoSpecies)
            .filter(VideoSpecies.bird_profile_id == int(profile_id))
            .order_by(VideoSpecies.id.desc())
            .limit(50)
            .all()
        )
        vecs: list[list[float]] = []
        for row in rows:
            emb = _fetch_anchor_embedding(video_species_id=int(row.id))
            if emb is not None:
                vecs.append(emb)
        anchor = _mean_normalized(vecs)
        if resolved_species_id is None and rows:
            resolved_species_id = rows[0].species_id

    if anchor is None:
        base["message"] = "anchor_embedding_missing"
        return base

    centroids = _profile_centroids(
        exclude_profile_id=profile_id,
        species_id=resolved_species_id,
    )
    if not centroids:
        base["available"] = True
        base["message"] = "no_profile_centroids"
        return base

    profiles = {
        int(p.id): p for p in db.session.query(BirdProfile).filter(BirdProfile.id.in_(list(centroids.keys()))).all()
    }
    scored: list[dict[str, Any]] = []
    for pid, centroid in centroids.items():
        score = _cosine(anchor, centroid)
        tier = _tier_for_score(score=score, cfg=cfg)
        if tier is None:
            continue
        prof = profiles.get(int(pid))
        scored.append(
            {
                "profile_id": int(pid),
                "display_name": prof.display_name if prof else f"#{pid}",
                "species_id": prof.species_id if prof else None,
                "avatar_url": prof.avatar_url if prof else None,
                "similarity": round(float(score), 6),
                "similarity_percent": int(round(max(0.0, min(1.0, score)) * 100)),
                "tier": tier,
                "status": prof.status if prof else None,
            }
        )
    scored.sort(key=lambda x: float(x["similarity"]), reverse=True)
    base["available"] = True
    base["candidates"] = scored[:lim]
    if video_species_id is not None:
        base["video_species_id"] = int(video_species_id)
    if profile_id is not None:
        base["profile_id"] = int(profile_id)
    return base


def record_link_feedback(
    *,
    action: str,
    candidate_profile_id: int,
    anchor_profile_id: int | None = None,
    video_species_id: int | None = None,
    similarity: float | None = None,
    source: str = "auto_link_ui",
) -> dict[str, Any]:
    act = str(action or "").strip().lower()
    if act not in {"confirm", "reject"}:
        raise ValueError("action must be confirm or reject")
    label = "positive" if act == "confirm" else "hard_negative"
    row = ReidTrainingPair(
        anchor_profile_id=int(anchor_profile_id) if anchor_profile_id is not None else None,
        candidate_profile_id=int(candidate_profile_id),
        anchor_video_species_id=int(video_species_id) if video_species_id is not None else None,
        similarity=float(similarity) if similarity is not None else None,
        label=label,
        source=str(source or "auto_link_ui")[:64],
    )
    db.session.add(row)
    db.session.commit()
    return {
        "ok": True,
        "label": label,
        "id": int(row.id),
        "created_at": row.created_at.astimezone(timezone.utc).isoformat() if row.created_at else None,
    }


def merge_bird_profiles(*, target_profile_id: int, source_profile_id: int) -> dict[str, Any]:
    target_id = int(target_profile_id)
    source_id = int(source_profile_id)
    if target_id == source_id:
        raise ValueError("cannot merge profile into itself")
    target = db.session.get(BirdProfile, target_id)
    source = db.session.get(BirdProfile, source_id)
    if target is None or source is None:
        raise LookupError("profile not found")
    updated = (
        db.session.query(VideoSpecies)
        .filter(VideoSpecies.bird_profile_id == source_id)
        .update(
            {"bird_profile_id": target_id, "individual_nickname": target.display_name},
            synchronize_session=False,
        )
    )
    db.session.delete(source)
    db.session.commit()
    return {
        "target_profile_id": target_id,
        "source_profile_id": source_id,
        "merged_detections": int(updated or 0),
        "display_name": target.display_name,
    }


def auto_link_hook(*, video_species_id: int) -> dict[str, Any]:
    """Lightweight hook after profile assignment — top auto-tier candidate only."""
    try:
        payload = suggest_profile_links(video_species_id=int(video_species_id), limit=1)
    except LookupError:
        return {
            "video_species_id": int(video_species_id),
            "candidate_profile_id": None,
            "strategy": "reid_embedding",
            "available": False,
        }
    candidates = payload.get("candidates") or []
    top = candidates[0] if candidates else None
    return {
        "video_species_id": int(video_species_id),
        "candidate_profile_id": int(top["profile_id"]) if top and top.get("tier") == "auto" else None,
        "similarity": top.get("similarity") if top else None,
        "tier": top.get("tier") if top else None,
        "strategy": "reid_embedding",
        "available": bool(payload.get("available")),
    }
