"""Add VideoSpecies.welfare_distance for welfare screening UI.

Revision ID: 025_welfare_distance
Revises: 024_video_camera_id
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "025_welfare_distance"
down_revision = "024_video_camera_id"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    insp = inspect(op.get_bind())
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    if "video_species" not in inspect(op.get_bind()).get_table_names():
        return
    cols = _column_names("video_species")
    if "welfare_distance" not in cols:
        op.add_column(
            "video_species",
            sa.Column("welfare_distance", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    if "video_species" not in inspect(op.get_bind()).get_table_names():
        return
    cols = _column_names("video_species")
    if "welfare_distance" in cols:
        op.drop_column("video_species", "welfare_distance")
