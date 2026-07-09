"""Add Video.camera_id for timeline / analytics camera filter.

Revision ID: 024_video_camera_id
Revises: 023_session_runtime_camera_slot
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "024_video_camera_id"
down_revision = "023_session_runtime_camera_slot"
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
    if "camera_id" not in cols:
        op.add_column(
            "video",
            sa.Column("camera_id", sa.String(length=64), nullable=True),
        )
    idx = {i.get("name") for i in inspect(op.get_bind()).get_indexes("video")}
    if "ix_video_camera_id" not in idx:
        op.create_index("ix_video_camera_id", "video", ["camera_id"])


def downgrade() -> None:
    if "video" not in inspect(op.get_bind()).get_table_names():
        return
    idx = {i.get("name") for i in inspect(op.get_bind()).get_indexes("video")}
    if "ix_video_camera_id" in idx:
        op.drop_index("ix_video_camera_id", table_name="video")
    cols = _column_names("video")
    if "camera_id" in cols:
        op.drop_column("video", "camera_id")
