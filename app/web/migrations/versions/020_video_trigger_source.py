"""Add Video.trigger_source for explicit timeline trigger semantics.

Revision ID: 020_video_trigger_source
Revises: 019_expert_review_queue
Create Date: 2026-05-31 22:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "020_video_trigger_source"
down_revision = "019_expert_review_queue"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    insp = inspect(op.get_bind())
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    if "video" not in inspect(op.get_bind()).get_table_names():
        return
    cols = _column_names("video")
    if "trigger_source" not in cols:
        op.add_column(
            "video",
            sa.Column("trigger_source", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    if "video" not in inspect(op.get_bind()).get_table_names():
        return
    cols = _column_names("video")
    if "trigger_source" in cols:
        op.drop_column("video", "trigger_source")
