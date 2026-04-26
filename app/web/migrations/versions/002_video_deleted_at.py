"""Add soft-delete marker for videos.

Revision ID: 005_video_deleted_at
Revises: 004_birdnet_fifo_event
Create Date: 2026-04-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "005_video_deleted_at"
down_revision = "004_birdnet_fifo_event"
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {idx["name"] for idx in insp.get_indexes(table)}


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name
    insp = inspect(conn)

    if "deleted_at" not in _column_names(insp, "video"):
        col = sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        if dialect == "sqlite":
            with op.batch_alter_table("video") as batch:
                batch.add_column(col)
        else:
            op.add_column("video", col)
        insp = inspect(conn)

    if "ix_video_deleted_at" not in _index_names(insp, "video"):
        op.create_index("ix_video_deleted_at", "video", ["deleted_at"])


def downgrade():
    pass
