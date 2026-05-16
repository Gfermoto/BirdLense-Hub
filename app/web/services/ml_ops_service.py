"""ML/CV operator helpers that work without new model weights."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import joinedload

from app_config.app_config import app_config
from models import Video, VideoSpecies
from util import ensure_utc

from services.reid_contract import EMBEDDING_SCHEMA_V1, embedding_age_hours
from services.reid_policy_service import load_reid_policy_config, policy_snapshot, evaluate_reid_candidate
from services.feedback_loop_service import (
    build_feedback_loop_status as _build_feedback_loop_status,
    export_feedback_learning_dataset as _export_feedback_learning_dataset,
)

_log = logging.getLogger(__name__)


def build_active_learning_pool_preview(session, *, limit: int = 100) -> tuple[dict[str, Any], int]:
    """Preview uncertain review items as AL pool candidates (#369)."""
    limit = min(max(int(limit or 100), 1), 500)
    rows = (
        session.query(VideoSpecies)
        .options(joinedload(VideoSpecies.video), joinedload(VideoSpecies.species))
        .filter(VideoSpecies.manually_corrected.is_(False))
        .filter(
            (VideoSpecies.classifier_needs_review.is_(True))
            | (VideoSpecies.review_reason.isnot(None))
            | (VideoSpecies.confidence < 0.5)
        )
        .order_by(VideoSpecies.created_at.desc(), VideoSpecies.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        items.append(
            {
                "video_species_id": row.id,
                "video_id": row.video_id,
                "video_path": getattr(row.video, "video_path", None),
                "species_name": getattr(row.species, "name", None),
                "track_id": row.track_id,
                "confidence": row.confidence,
                "review_reason": row.review_reason,
                "classifier_entropy": row.classifier_entropy,
                "classifier_top1_top2_margin": row.classifier_top1_top2_margin,
                "classifier_needs_review": bool(row.classifier_needs_review),
            }
        )
    return {
        "schema": "active_learning_pool_preview@v1",
        "count": len(items),
        "items": items,
    }, 200


def build_reid_summary(session) -> tuple[dict[str, Any], int]:
    """Read-only summary of offline Re-ID sidecar table (#374)."""
    try:
        exists = session.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reid_embedding'")
        ).scalar()
    except Exception:
        _log.debug("reid_embedding sqlite_master probe failed", exc_info=True)
        exists = None
    if not exists:
        return {
            "schema": "reid_summary@v2",
            "available": False,
            "embedding_count": 0,
            "recent": [],
            "contract": {
                "expected_schema": EMBEDDING_SCHEMA_V1,
                "schema_mix_ok": True,
                "schema_counts": {},
                "model_id_counts": {},
                "dim_counts": {},
                "model_sha16_counts": {},
                "missing_contract_rows": 0,
                "max_embedding_age_hours": None,
                "status": "missing_table",
            },
        }, 200

    count = int(session.execute(text("SELECT COUNT(*) FROM reid_embedding")).scalar() or 0)
    try:
        info_rows = session.execute(text("PRAGMA table_info(reid_embedding)")).fetchall()
        col_names = {str(r[1]) for r in info_rows}
    except Exception:
        _log.debug("reid_embedding PRAGMA table_info failed", exc_info=True)
        col_names = set()

    select_cols = [
        "id",
        "video_id",
        "video_species_id",
        "species_id",
        "track_id",
    ]
    optional_cols = [
        "embedding_schema",
        "embedding_model_id",
        "embedding_model_sha16",
        "dim",
        "jsonl_created_at_utc",
        "created_at",
    ]
    for c in optional_cols:
        if c in col_names:
            select_cols.append(c)

    try:
        rows = (
            session.execute(
                text(
                    f"SELECT {', '.join(select_cols)} FROM reid_embedding ORDER BY id DESC LIMIT 20"  # nosec B608
                ),
            )
            .mappings()
            .all()
        )
    except Exception:
        _log.debug("reid_embedding recent sample query failed", exc_info=True)
        rows = []
    contract: dict[str, Any] = {
        "expected_schema": EMBEDDING_SCHEMA_V1,
        "schema_mix_ok": True,
        "schema_counts": {},
        "model_id_counts": {},
        "dim_counts": {},
        "model_sha16_counts": {},
        "missing_contract_rows": 0,
        "max_embedding_age_hours": None,
        "status": "ok",
    }
    required_for_contract = {
        "embedding_schema",
        "embedding_model_id",
        "embedding_model_sha16",
        "crop_fingerprint_sha16",
        "jsonl_created_at_utc",
    }
    if not required_for_contract.issubset(col_names):
        contract["status"] = "legacy_table"
        contract["issues"] = ["reid_embedding_missing_contract_columns"]
        contract["schema_mix_ok"] = False
    else:
        try:
            schema_rows = (
                session.execute(
                    text(
                        "SELECT embedding_schema AS embedding_schema, COUNT(*) AS c "
                        "FROM reid_embedding GROUP BY embedding_schema"
                    )
                )
                .mappings()
                .all()
            )
            contract["schema_counts"] = {str(r["embedding_schema"] or ""): int(r["c"]) for r in schema_rows}

            model_rows = (
                session.execute(
                    text(
                        "SELECT embedding_model_id AS embedding_model_id, COUNT(*) AS c "
                        "FROM reid_embedding GROUP BY embedding_model_id"
                    )
                )
                .mappings()
                .all()
            )
            contract["model_id_counts"] = {str(r["embedding_model_id"] or ""): int(r["c"]) for r in model_rows}

            dim_rows = (
                session.execute(text("SELECT dim AS dim, COUNT(*) AS c FROM reid_embedding GROUP BY dim"))
                .mappings()
                .all()
            )
            contract["dim_counts"] = {str(int(r["dim"])): int(r["c"]) for r in dim_rows}

            sha_rows = (
                session.execute(
                    text(
                        "SELECT embedding_model_sha16 AS embedding_model_sha16, COUNT(*) AS c "
                        "FROM reid_embedding GROUP BY embedding_model_sha16"
                    )
                )
                .mappings()
                .all()
            )
            contract["model_sha16_counts"] = {str(r["embedding_model_sha16"] or ""): int(r["c"]) for r in sha_rows}

            missing = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM reid_embedding WHERE embedding_schema IS NULL "
                        "OR trim(embedding_schema) = '' OR embedding_model_id IS NULL "
                        "OR trim(embedding_model_id) = '' OR embedding_model_sha16 IS NULL "
                        "OR trim(embedding_model_sha16) = '' OR crop_fingerprint_sha16 IS NULL "
                        "OR trim(crop_fingerprint_sha16) = '' OR jsonl_created_at_utc IS NULL "
                        "OR trim(jsonl_created_at_utc) = ''"
                    )
                ).scalar()
                or 0
            )
            contract["missing_contract_rows"] = missing

            freshness_rows = (
                session.execute(
                    text(
                        "SELECT jsonl_created_at_utc AS ts FROM reid_embedding "
                        "WHERE jsonl_created_at_utc IS NOT NULL AND trim(jsonl_created_at_utc) != '' "
                        "ORDER BY id DESC LIMIT 5000"
                    )
                )
                .mappings()
                .all()
            )
            ages = [embedding_age_hours(str(r["ts"])) for r in freshness_rows]
            ages = [a for a in ages if a is not None]
            contract["max_embedding_age_hours"] = max(ages) if ages else None

            distinct_schema_keys = {k for k in contract["schema_counts"].keys() if k}
            non_empty_models = {k for k in contract["model_id_counts"].keys() if k}
            distinct_dims = {int(k) for k in contract["dim_counts"].keys() if str(k).isdigit()}
            issues: list[str] = []
            if missing > 0:
                issues.append("incomplete_contract_metadata")
            if len(distinct_schema_keys) > 1:
                issues.append("mixed_embedding_schema")
                contract["schema_mix_ok"] = False
            if len(non_empty_models) > 1:
                issues.append("mixed_embedding_model_id")
                contract["schema_mix_ok"] = False
            if len(distinct_dims) > 1:
                issues.append("mixed_embedding_dim")
                contract["schema_mix_ok"] = False
            stale_hours = app_config.get("processor.reid_max_embedding_age_hours")
            try:
                stale_hours_f = float(stale_hours) if stale_hours is not None else None
            except (TypeError, ValueError):
                stale_hours_f = None
            if stale_hours_f is not None and contract["max_embedding_age_hours"] is not None:
                if float(contract["max_embedding_age_hours"]) > stale_hours_f:
                    issues.append("stale_embeddings")
            if issues:
                contract["status"] = "degraded"
                contract["issues"] = issues
        except Exception:
            _log.debug("reid_embedding contract aggregation failed", exc_info=True)
            contract["status"] = "unknown"
    return {
        "schema": "reid_summary@v2",
        "available": True,
        "embedding_count": count,
        "recent": [dict(r) for r in rows],
        "contract": contract,
    }, 200


def build_ml_runtime_status() -> tuple[dict[str, Any], int]:
    """Operator-facing ML/CV runtime config state (#373/#372)."""
    return {
        "schema": "ml_runtime_status@v1",
        "video": {
            "encoding": app_config.get("video.encoding"),
            "record_with_vaapi": app_config.get("video.record_with_vaapi"),
            "capture_backend_config": app_config.get("video.capture_backend"),
        },
        "processor": {
            "inference_backend": app_config.get("processor.inference_backend"),
            "classifier_inference_backend": app_config.get("processor.classifier_inference_backend"),
            "detector_weight_contract": app_config.get("processor.detector_weight_contract"),
            "binary_imgsz": app_config.get("processor.binary_imgsz"),
            "frame_processing_warn_ms": app_config.get("processor.frame_processing_warn_ms"),
        },
    }, 200


def build_feedback_loop_status_payload(session) -> tuple[dict[str, Any], int]:
    """Operator status for feedback-learning loop exports (#397)."""
    data_dir = str(app_config.get("directories.data") or "data")
    return _build_feedback_loop_status(session, data_dir=data_dir), 200


def build_feedback_loop_export_payload(payload: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    """Run feedback-learning export and return artifact summary (#397)."""
    data_dir = str(app_config.get("directories.data") or "data")
    p = payload or {}
    try:
        since_hours = int(p.get("since_hours", 24))
    except (TypeError, ValueError):
        return {"error": "since_hours must be an integer"}, 400
    try:
        limit = int(p.get("limit", 5000))
    except (TypeError, ValueError):
        return {"error": "limit must be an integer"}, 400
    dry_run = bool(p.get("dry_run", False))
    export_tag = (p.get("export_tag") or "").strip() if isinstance(p.get("export_tag"), str) else ""
    if since_hours <= 0:
        return {"error": "since_hours must be > 0"}, 400
    if limit <= 0:
        return {"error": "limit must be > 0"}, 400

    try:
        out = _export_feedback_learning_dataset(
            db_path=f"{data_dir}/db/birdlense.db",
            data_dir=data_dir,
            output_dir=f"{data_dir}/feedback_exports",
            since_hours=since_hours,
            limit=limit,
            dry_run=dry_run,
            export_tag=export_tag or None,
        )
        return out, 200
    except Exception as exc:
        _log.exception("feedback learning export failed")
        latest_status = Path(f"{data_dir}/feedback_exports/latest_status.json")
        latest_status.parent.mkdir(parents=True, exist_ok=True)
        latest_status.write_text(
            json.dumps(
                {
                    "schema": "feedback_learning_latest_status@v1",
                    "status": "error",
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "schema": "feedback_learning_export@v1",
            "status": "error",
            "error": str(exc),
        }, 500


def _cosine(a: list[float], b: list[float]) -> float:
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


def build_video_reid_match_payload(session, video_id: int) -> tuple[dict[str, Any], int]:
    """Minimal per-track Re-ID matches for product UI hints."""
    video = session.get(Video, int(video_id))
    if not video:
        return {"error": "Video not found"}, 404

    policy_cfg = load_reid_policy_config()
    base_payload: dict[str, Any] = {
        "schema": "video_reid_match@v2",
        "policy": policy_snapshot(),
        "video_id": int(video_id),
    }

    has_reid = bool(
        session.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reid_embedding'")).scalar()
    )
    if not has_reid:
        return {
            **base_payload,
            "available": False,
            "matches": [],
            "message": "reid_embedding_table_missing",
        }, 200

    try:
        info_rows = session.execute(text("PRAGMA table_info(reid_embedding)")).fetchall()
        reid_cols = {str(r[1]) for r in info_rows}
    except Exception:
        _log.debug("video_reid_match PRAGMA table_info failed", exc_info=True)
        reid_cols = set()

    rows = (
        session.query(VideoSpecies)
        .options(joinedload(VideoSpecies.species))
        .filter(VideoSpecies.video_id == int(video_id))
        .filter(VideoSpecies.source == "video")
        .all()
    )
    if not rows:
        return {
            **base_payload,
            "available": True,
            "matches": [],
        }, 200

    needs_contract_cols = {
        "embedding_schema",
        "embedding_model_id",
        "embedding_model_sha16",
        "crop_fingerprint_sha16",
        "jsonl_created_at_utc",
    }
    contract_ready = needs_contract_cols.issubset(reid_cols)

    emb_cols = ["embedding_json"]
    for c in (
        "embedding_schema",
        "embedding_model_id",
        "embedding_model_sha16",
        "crop_fingerprint_sha16",
        "jsonl_created_at_utc",
        "dim",
    ):
        if c in reid_cols:
            emb_cols.append(c)

    def _fetch_emb_row(vsid: int) -> dict[str, Any] | None:
        row = (
            session.execute(
                text(
                    f"SELECT {', '.join(emb_cols)} FROM reid_embedding "  # nosec B608
                    "WHERE video_species_id = :vsid ORDER BY id DESC LIMIT 1"
                ),
                {"vsid": int(vsid)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    video_ids_needed: set[int] = {int(video_id)}
    for det in rows:
        video_ids_needed.add(int(det.video_id))

    starts: dict[int, Any] = {}
    paths: dict[int, str | None] = {}
    if video_ids_needed:
        q = session.query(Video.id, Video.start_time, Video.video_path).filter(Video.id.in_(sorted(video_ids_needed)))
        for vid, st, vp in q.all():
            starts[int(vid)] = st
            paths[int(vid)] = vp

    out: list[dict[str, Any]] = []
    for det in rows:
        anchor_row = _fetch_emb_row(int(det.id))
        if not anchor_row:
            continue
        anchor = _parse_embedding(anchor_row.get("embedding_json"))
        if not anchor:
            continue

        cands = (
            session.execute(
                text(
                    "SELECT video_species_id, video_id, track_id, species_name, individual_label, embedding_json "  # nosec B608
                    + (
                        ", embedding_schema, embedding_model_id, embedding_model_sha16, "
                        "crop_fingerprint_sha16, jsonl_created_at_utc, dim "
                        if contract_ready
                        else ""
                    )
                    + " FROM reid_embedding "
                    "WHERE species_id = :sid AND video_species_id != :vsid AND video_id != :vid "
                    "ORDER BY id DESC LIMIT 200"
                ),
                {"sid": det.species_id, "vsid": det.id, "vid": int(video_id)},
            )
            .mappings()
            .all()
        )
        best = None
        best_score = -1.0
        best_full = None
        for c in cands:
            emb = _parse_embedding(c.get("embedding_json"))
            if not emb:
                continue
            score = _cosine(anchor, emb)
            if score > best_score:
                best_score = score
                best = c
                best_full = dict(c)
        if not best or best_full is None:
            continue

        species_name = det.species.name if det.species else None
        cand_vid = int(best.get("video_id") or 0)
        hours_apart = None
        try:
            a0 = starts.get(int(video_id))
            a1 = starts.get(cand_vid)
            if a0 is not None and a1 is not None:
                hours_apart = abs((ensure_utc(a1) - ensure_utc(a0)).total_seconds()) / 3600.0
        except Exception:
            _log.debug("reid hours_apart from video starts failed", exc_info=True)
            hours_apart = None

        if not contract_ready:
            continue

        dec = evaluate_reid_candidate(
            cfg=policy_cfg,
            species_name=species_name,
            similarity=float(best_score),
            anchor_video_path=paths.get(int(video_id)),
            candidate_video_path=paths.get(cand_vid),
            anchor_created_at=str(anchor_row.get("jsonl_created_at_utc") or ""),
            candidate_created_at=str(best_full.get("jsonl_created_at_utc") or ""),
            anchor_schema=str(anchor_row.get("embedding_schema") or ""),
            cand_schema=str(best_full.get("embedding_schema") or ""),
            anchor_model_id=str(anchor_row.get("embedding_model_id") or ""),
            cand_model_id=str(best_full.get("embedding_model_id") or ""),
            anchor_dim=int(anchor_row["dim"]) if anchor_row.get("dim") is not None else None,
            cand_dim=int(best_full["dim"]) if best_full.get("dim") is not None else None,
            anchor_model_sha16=str(anchor_row.get("embedding_model_sha16") or ""),
            cand_model_sha16=str(best_full.get("embedding_model_sha16") or ""),
            anchor_crop_fp=str(anchor_row.get("crop_fingerprint_sha16") or ""),
            cand_crop_fp=str(best_full.get("crop_fingerprint_sha16") or ""),
            hours_apart=hours_apart,
        )
        if dec.decision != "suggest_same_individual":
            continue

        cross_camera = False
        ap = paths.get(int(video_id))
        bp = paths.get(cand_vid)
        if ap and bp:
            cross_camera = str(ap).replace("\\", "/").rsplit("/", 1)[0] != str(bp).replace("\\", "/").rsplit("/", 1)[0]

        out.append(
            {
                "video_species_id": det.id,
                "track_id": det.track_id,
                "species_name": species_name,
                "individual_nickname": det.individual_nickname,
                "candidate_video_species_id": best.get("video_species_id"),
                "candidate_video_id": best.get("video_id"),
                "candidate_track_id": best.get("track_id"),
                "candidate_species_name": best.get("species_name"),
                "candidate_nickname": best.get("individual_label"),
                "similarity": round(float(best_score), 4),
                "decision": "suggest_same_individual",
                "policy_decision": dec.decision,
                "policy_reasons": dec.reasons,
                "effective_threshold": dec.effective_threshold,
                "cross_camera": cross_camera,
                "hours_apart": hours_apart,
            }
        )

    return {
        **base_payload,
        "available": True,
        "matches": out,
        "contract_ready": bool(contract_ready),
    }, 200
