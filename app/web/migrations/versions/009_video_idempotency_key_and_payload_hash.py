"""Add video idempotency key and payload hash for strict ingest dedup.

Revision ID: 009_video_idempotency_key_and_payload_hash
Revises: 008_feedback_learning_events
Create Date: 2026-05-03
"""

from __future__ import annotations

import hashlib
from datetime import timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "009_video_idempotency_key_and_payload_hash"
down_revision = "008_feedback_learning_events"
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _iso_utc_naive(value) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if getattr(value, "tzinfo", None) is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat()


def _base_clip_key(processor_version, video_path, start_time, end_time) -> str:
    seed = "|".join(
        [
            str(processor_version or "").strip(),
            str(video_path or "").strip(),
            _iso_utc_naive(start_time),
            _iso_utc_naive(end_time),
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if "video" not in insp.get_table_names():
        return

    cols = _column_names(insp, "video")
    dialect = conn.dialect.name
    if "idempotency_key" not in cols:
        col = sa.Column("idempotency_key", sa.String(length=96), nullable=True)
        if dialect == "sqlite":
            with op.batch_alter_table("video") as batch:
                batch.add_column(col)
        else:
            op.add_column("video", col)
    if "ingest_payload_hash" not in cols:
        col = sa.Column("ingest_payload_hash", sa.String(length=64), nullable=True)
        if dialect == "sqlite":
            with op.batch_alter_table("video") as batch:
                batch.add_column(col)
        else:
            op.add_column("video", col)

    rows = conn.execute(
        sa.text(
            "SELECT id, processor_version, video_path, start_time, end_time, idempotency_key FROM video ORDER BY id ASC"
        )
    ).mappings()
    used: set[str] = set()
    for row in rows:
        existing = str(row.get("idempotency_key") or "").strip()
        if existing and existing not in used:
            used.add(existing)
            continue
        base_key = _base_clip_key(
            row.get("processor_version"),
            row.get("video_path"),
            row.get("start_time"),
            row.get("end_time"),
        )
        key = base_key
        if key in used:
            key = f"{base_key[:80]}:{int(row['id'])}"
        used.add(key)
        conn.execute(
            sa.text("UPDATE video SET idempotency_key = :key WHERE id = :id"),
            {"key": key, "id": int(row["id"])},
        )

    idx_names = {idx["name"] for idx in insp.get_indexes("video")}
    if "ix_video_idempotency_key" not in idx_names:
        op.create_index("ix_video_idempotency_key", "video", ["idempotency_key"], unique=True)

    with op.batch_alter_table("video") as batch:
        batch.alter_column("idempotency_key", existing_type=sa.String(length=96), nullable=False)


def downgrade():
    pass
