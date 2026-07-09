"""Persist multimodal fusion evidence on video_species.

Revision ID: 026_video_species_multimodal_evidence
Revises: 025_welfare_distance
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "026_video_species_multimodal_evidence"
down_revision = "025_welfare_distance"
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
    if "audio_evidence" not in cols:
        op.add_column(
            "video_species",
            sa.Column("audio_evidence", sa.String(length=16), nullable=True),
        )
    if "birdnet_prior" not in cols:
        op.add_column(
            "video_species",
            sa.Column("birdnet_prior", sa.Float(), nullable=True),
        )
    if "weighted_arbiter_score" not in cols:
        op.add_column(
            "video_species",
            sa.Column("weighted_arbiter_score", sa.Float(), nullable=True),
        )
    if "hint_trace" not in cols:
        op.add_column(
            "video_species",
            sa.Column("hint_trace", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if "video_species" not in inspect(op.get_bind()).get_table_names():
        return
    cols = _column_names("video_species")
    for name in ("hint_trace", "weighted_arbiter_score", "birdnet_prior", "audio_evidence"):
        if name in cols:
            op.drop_column("video_species", name)
