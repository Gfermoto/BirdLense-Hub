"""ReID triplet mining feedback pairs for auto-link UI.

Revision ID: 018_reid_training_pairs
Revises: 017_global_bird_profiles
Create Date: 2026-05-18 20:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "018_reid_training_pairs"
down_revision = "017_global_bird_profiles"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _index_names(table: str) -> set[str]:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    if "reid_training_pairs" not in _table_names():
        op.create_table(
            "reid_training_pairs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("anchor_profile_id", sa.Integer(), nullable=True),
            sa.Column("candidate_profile_id", sa.Integer(), nullable=True),
            sa.Column("anchor_video_species_id", sa.Integer(), nullable=True),
            sa.Column("candidate_video_species_id", sa.Integer(), nullable=True),
            sa.Column("similarity", sa.Float(), nullable=True),
            sa.Column("label", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="auto_link_ui"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["anchor_profile_id"], ["bird_profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["candidate_profile_id"], ["bird_profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["anchor_video_species_id"], ["video_species.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["candidate_video_species_id"], ["video_species.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    idx = _index_names("reid_training_pairs")
    if "ix_reid_training_pairs_label" not in idx:
        op.create_index("ix_reid_training_pairs_label", "reid_training_pairs", ["label"], unique=False)
    if "ix_reid_training_pairs_created_at" not in idx:
        op.create_index(
            "ix_reid_training_pairs_created_at",
            "reid_training_pairs",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    if "reid_training_pairs" not in _table_names():
        return
    idx = _index_names("reid_training_pairs")
    if "ix_reid_training_pairs_created_at" in idx:
        op.drop_index("ix_reid_training_pairs_created_at", table_name="reid_training_pairs")
    if "ix_reid_training_pairs_label" in idx:
        op.drop_index("ix_reid_training_pairs_label", table_name="reid_training_pairs")
    op.drop_table("reid_training_pairs")
