"""Backfill ingest payload hash and make idempotency unique only for active videos.

Revision ID: 010_backfill_ingest_payload_hash_and_partial_idempotency
Revises: 009_video_idempotency_key_and_payload_hash
Create Date: 2026-05-03
"""

from __future__ import annotations

import hashlib
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "010_backfill_ingest_payload_hash_and_partial_idempotency"
down_revision = "009_video_idempotency_key_and_payload_hash"
branch_labels = None
depends_on = None


def _payload_hash(rows: list[dict]) -> str:
    def _canonical_frames(value):
        if value is None:
            return []
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return value
        return value

    normalized = []
    for row in rows:
        normalized.append(
            {
                "species_name": str(row.get("species_name") or "").strip(),
                "source": str(row.get("source") or "").strip(),
                "detection_provider": str(row.get("detection_provider") or "").strip(),
                "track_id": row.get("track_id"),
                "start_time": float(row.get("start_time") or 0.0),
                "end_time": float(row.get("end_time") or 0.0),
                "confidence": float(row.get("confidence") or 0.0),
                "visit_eligible": bool(row.get("visit_eligible", True)),
                "notification_eligible": bool(row.get("notification_eligible", True)),
                "decision_kind": str(row.get("decision_kind") or "").strip(),
                "classifier_confidence": float(row.get("classifier_confidence") or 0.0),
                "classifier_entropy": float(row.get("classifier_entropy") or 0.0),
                "classifier_top1_top2_margin": float(row.get("classifier_top1_top2_margin") or 0.0),
                "classifier_needs_review": bool(row.get("classifier_needs_review", False)),
                "review_reason": str(row.get("review_reason") or "").strip(),
                "individual_nickname": str(row.get("individual_nickname") or "").strip(),
                "frames": _canonical_frames(row.get("frames")),
            }
        )
    normalized.sort(
        key=lambda item: (
            item["species_name"],
            item["source"],
            item["detection_provider"],
            item["track_id"] if item["track_id"] is not None else -1,
            item["start_time"],
            item["end_time"],
            item["confidence"],
            item["visit_eligible"],
            item["notification_eligible"],
            item["decision_kind"],
            item["classifier_confidence"],
            item["classifier_entropy"],
            item["classifier_top1_top2_margin"],
            item["classifier_needs_review"],
            item["review_reason"],
            item["individual_nickname"],
            json.dumps(item["frames"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    )
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if "video" not in insp.get_table_names():
        return

    video_rows = conn.execute(
        sa.text('SELECT id FROM video WHERE ingest_payload_hash IS NULL OR ingest_payload_hash = "" ORDER BY id ASC')
    ).mappings()
    for row in video_rows:
        video_id = int(row["id"])
        detection_rows = conn.execute(
            sa.text(
                "SELECT s.name AS species_name, vs.source, vs.detection_provider, vs.track_id, "
                "vs.start_time, vs.end_time, vs.confidence, "
                "vs.species_visit_id, vs.classifier_entropy, vs.classifier_top1_top2_margin, "
                "vs.classifier_needs_review, vs.review_reason, vs.individual_nickname, vs.frames "
                "FROM video_species vs "
                "JOIN species s ON s.id = vs.species_id "
                "WHERE vs.video_id = :video_id "
                "ORDER BY vs.id ASC"
            ),
            {"video_id": video_id},
        ).mappings()
        rows_for_hash = []
        for detection in detection_rows:
            rows_for_hash.append(
                {
                    "species_name": detection.get("species_name"),
                    "source": detection.get("source"),
                    "detection_provider": detection.get("detection_provider"),
                    "track_id": detection.get("track_id"),
                    "start_time": detection.get("start_time"),
                    "end_time": detection.get("end_time"),
                    "confidence": detection.get("confidence"),
                    "visit_eligible": detection.get("species_visit_id") is not None,
                    "notification_eligible": detection.get("species_visit_id") is not None,
                    "decision_kind": "",
                    "classifier_confidence": 0.0,
                    "classifier_entropy": detection.get("classifier_entropy"),
                    "classifier_top1_top2_margin": detection.get("classifier_top1_top2_margin"),
                    "classifier_needs_review": detection.get("classifier_needs_review"),
                    "review_reason": detection.get("review_reason"),
                    "individual_nickname": detection.get("individual_nickname"),
                    "frames": detection.get("frames"),
                }
            )
        payload_hash = _payload_hash(rows_for_hash)
        conn.execute(
            sa.text("UPDATE video SET ingest_payload_hash = :payload_hash WHERE id = :video_id"),
            {"payload_hash": payload_hash, "video_id": video_id},
        )

    idx_names = {idx["name"] for idx in inspect(conn).get_indexes("video")}
    if "ix_video_idempotency_key" in idx_names:
        op.drop_index("ix_video_idempotency_key", table_name="video")
    idx_names = {idx["name"] for idx in inspect(conn).get_indexes("video")}
    if "ux_video_idempotency_active" not in idx_names:
        op.create_index(
            "ux_video_idempotency_active",
            "video",
            ["idempotency_key"],
            unique=True,
            sqlite_where=sa.text("deleted_at IS NULL"),
            postgresql_where=sa.text("deleted_at IS NULL"),
        )


def downgrade():
    pass
