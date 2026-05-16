"""Optional video-level behavior label from processor baseline (#416).

Revision ID: 011_video_behavior_recognition
Revises: 010_backfill_ingest_payload_hash_and_partial_idempotency
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "011_video_behavior_recognition"
down_revision = "010_backfill_ingest_payload_hash_and_partial_idempotency"
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name
    insp = inspect(conn)
    cols = _column_names(insp, "video")
    label_col = sa.Column("behavior_label", sa.String(32), nullable=True)
    conf_col = sa.Column("behavior_confidence", sa.Float(), nullable=True)
    if dialect == "sqlite":
        with op.batch_alter_table("video") as batch:
            if "behavior_label" not in cols:
                batch.add_column(label_col)
            if "behavior_confidence" not in cols:
                batch.add_column(conf_col)
    else:
        if "behavior_label" not in cols:
            op.add_column("video", label_col)
        if "behavior_confidence" not in cols:
            op.add_column("video", conf_col)


def downgrade():
    pass
