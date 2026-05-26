"""Greedy ReID track clustering from ``reid_embedding`` sidecar (SOTA-13)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from app_config.app_config import app_config
from models import db


@dataclass
class TrackEmbeddingRow:
    video_species_id: int
    video_id: int
    species_id: int | None
    species_name: str | None
    track_id: int | None
    track_duration_sec: float
    embedding: list[float]


@dataclass
class ReidTrackCluster:
    cluster_id: str
    species_id: int | None
    member_video_species_ids: list[int] = field(default_factory=list)
    centroid_similarity: float = 1.0


def reid_gallery_enabled() -> bool:
    return _cfg_bool("processor.reid_gallery_enabled", False)


def reid_track_clustering_enabled() -> bool:
    if not reid_gallery_enabled():
        return False
    return _cfg_bool("processor.reid_track_clustering_enabled", False)


def _cfg_bool(key: str, default: bool) -> bool:
    raw = app_config.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _cfg_float(key: str, default: float) -> float:
    try:
        raw = app_config.get(key)
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def load_cluster_config() -> dict[str, Any]:
    return {
        "merge_threshold": _cfg_float("processor.reid_gallery_merge_cosine_threshold", 0.92),
        "duplicate_low": _cfg_float("processor.reid_gallery_duplicate_threshold_low", 0.82),
        "min_track_duration_sec": _cfg_float("processor.reid_gallery_min_track_duration_sec", 0.6),
        "max_members": int(_cfg_float("processor.reid_gallery_max_cluster_members", 24)),
    }


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0.0 or nb <= 0.0:
        return -1.0
    return dot / (na * nb)


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


def _reid_table_ready() -> bool:
    try:
        return bool(
            db.session.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reid_embedding'")
            ).scalar()
        )
    except Exception:
        return False


def load_track_embeddings(
    *,
    video_id: int | None = None,
    species_id: int | None = None,
    limit: int = 500,
) -> list[TrackEmbeddingRow]:
    if not _reid_table_ready():
        return []
    cfg = load_cluster_config()
    lim = max(1, min(int(limit or 500), 2000))
    clauses = ["re.embedding_json IS NOT NULL", "vs.id IS NOT NULL"]
    params: dict[str, Any] = {"min_dur": float(cfg["min_track_duration_sec"])}
    if video_id is not None:
        clauses.append("re.video_id = :video_id")
        params["video_id"] = int(video_id)
    if species_id is not None:
        clauses.append("re.species_id = :species_id")
        params["species_id"] = int(species_id)
    where = " AND ".join(clauses)
    sql = text(
        f"""
        SELECT
            vs.id AS video_species_id,
            re.video_id AS video_id,
            re.species_id AS species_id,
            re.species_name AS species_name,
            vs.track_id AS track_id,
            MAX(0.0, vs.end_time - vs.start_time) AS track_duration_sec,
            re.embedding_json AS embedding_json
        FROM reid_embedding re
        JOIN video_species vs ON vs.id = re.video_species_id
        WHERE {where}
          AND (vs.end_time - vs.start_time) >= :min_dur
        ORDER BY re.id DESC
        LIMIT {lim}
        """
    )
    rows = db.session.execute(sql, params).fetchall()
    out: list[TrackEmbeddingRow] = []
    for row in rows:
        emb = _parse_embedding(row.embedding_json)
        if not emb:
            continue
        out.append(
            TrackEmbeddingRow(
                video_species_id=int(row.video_species_id),
                video_id=int(row.video_id),
                species_id=int(row.species_id) if row.species_id is not None else None,
                species_name=str(row.species_name) if row.species_name else None,
                track_id=int(row.track_id) if row.track_id is not None else None,
                track_duration_sec=float(row.track_duration_sec or 0.0),
                embedding=emb,
            )
        )
    return out


def cluster_track_embeddings(rows: list[TrackEmbeddingRow]) -> list[ReidTrackCluster]:
    """Greedy clustering within species by cosine similarity."""
    if not rows:
        return []
    cfg = load_cluster_config()
    merge_thr = float(cfg["merge_threshold"])
    max_members = int(cfg["max_members"])
    by_species: dict[int | None, list[TrackEmbeddingRow]] = {}
    for row in rows:
        by_species.setdefault(row.species_id, []).append(row)

    clusters: list[ReidTrackCluster] = []
    cluster_idx = 0
    for species_id, members in by_species.items():
        remaining = list(members)
        while remaining:
            seed = remaining.pop(0)
            cluster_members = [seed]
            centroid = list(seed.embedding)
            i = 0
            while i < len(remaining):
                cand = remaining[i]
                if species_id is not None and cand.species_id != species_id:
                    i += 1
                    continue
                sim = cosine_similarity(centroid, cand.embedding)
                if sim >= merge_thr and len(cluster_members) < max_members:
                    cluster_members.append(cand)
                    remaining.pop(i)
                    dim = len(centroid)
                    centroid = [
                        (centroid[j] * (len(cluster_members) - 1) + cand.embedding[j])
                        / len(cluster_members)
                        for j in range(dim)
                    ]
                    norm = math.sqrt(sum(v * v for v in centroid))
                    if norm > 0:
                        centroid = [v / norm for v in centroid]
                else:
                    i += 1
            cluster_idx += 1
            min_sim = 1.0
            if len(cluster_members) > 1:
                sims = []
                for a in range(len(cluster_members)):
                    for b in range(a + 1, len(cluster_members)):
                        sims.append(
                            cosine_similarity(
                                cluster_members[a].embedding,
                                cluster_members[b].embedding,
                            )
                        )
                min_sim = min(sims) if sims else 1.0
            clusters.append(
                ReidTrackCluster(
                    cluster_id=f"s{species_id or 0}-c{cluster_idx}",
                    species_id=species_id,
                    member_video_species_ids=[m.video_species_id for m in cluster_members],
                    centroid_similarity=round(min_sim, 4),
                )
            )
    return clusters


def build_gallery_payload(
    *,
    video_id: int | None = None,
    species_id: int | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    if not reid_track_clustering_enabled():
        return {
            "enabled": False,
            "clusters": [],
            "message": "reid_gallery_disabled",
        }
    rows = load_track_embeddings(video_id=video_id, species_id=species_id, limit=limit)
    clusters = cluster_track_embeddings(rows)
    row_by_id = {r.video_species_id: r for r in rows}
    cluster_payload = []
    for cl in clusters:
        members = []
        for vs_id in cl.member_video_species_ids:
            r = row_by_id.get(vs_id)
            if not r:
                continue
            members.append(
                {
                    "video_species_id": r.video_species_id,
                    "video_id": r.video_id,
                    "track_id": r.track_id,
                    "track_duration_sec": round(r.track_duration_sec, 3),
                    "species_name": r.species_name,
                }
            )
        cluster_payload.append(
            {
                "cluster_id": cl.cluster_id,
                "species_id": cl.species_id,
                "min_pairwise_similarity": cl.centroid_similarity,
                "member_count": len(members),
                "members": members,
            }
        )
    return {
        "enabled": True,
        "config": load_cluster_config(),
        "embedding_rows": len(rows),
        "clusters": cluster_payload,
    }
