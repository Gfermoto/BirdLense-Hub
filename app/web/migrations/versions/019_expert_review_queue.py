"""Expert review queue for ReID gallery and track merge workflow (SOTA-13).

Revision ID: 019_expert_review_queue
Revises: 018_reid_training_pairs
Create Date: 2026-05-26 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "019_expert_review_queue"
down_revision = "018_reid_training_pairs"
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
    if "expert_review_queue" not in _table_names():
        op.create_table(
            "expert_review_queue",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_type", sa.String(length=48), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("video_species_id", sa.Integer(), nullable=True),
            sa.Column("related_video_species_id", sa.Integer(), nullable=True),
            sa.Column("cluster_key", sa.String(length=128), nullable=True),
            sa.Column("similarity", sa.Float(), nullable=True),
            sa.Column("species_id", sa.Integer(), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["video_species_id"], ["video_species.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["related_video_species_id"], ["video_species.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["species_id"], ["species.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    idx = _index_names("expert_review_queue")
    if "ix_expert_review_queue_status_created" not in idx:
        op.create_index(
            "ix_expert_review_queue_status_created",
            "expert_review_queue",
            ["status", "created_at"],
            unique=False,
        )
    if "ix_expert_review_queue_cluster_key" not in idx:
        op.create_index(
            "ix_expert_review_queue_cluster_key",
            "expert_review_queue",
            ["cluster_key"],
            unique=False,
        )


def downgrade() -> None:
    if "expert_review_queue" not in _table_names():
        return
    idx = _index_names("expert_review_queue")
    if "ix_expert_review_queue_cluster_key" in idx:
        op.drop_index("ix_expert_review_queue_cluster_key", table_name="expert_review_queue")
    if "ix_expert_review_queue_status_created" in idx:
        op.drop_index("ix_expert_review_queue_status_created", table_name="expert_review_queue")
    op.drop_table("expert_review_queue")
