"""Add detection feedback events table for learning loop (#397).

Revision ID: 008_feedback_learning_events
Revises: 007_videospecies_individual_nickname
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "008_feedback_learning_events"
down_revision = "007_videospecies_individual_nickname"
branch_labels = None
depends_on = None


def _has_table(insp, table: str) -> bool:
    return table in insp.get_table_names()


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if _has_table(insp, "detection_feedback_event"):
        return

    op.create_table(
        "detection_feedback_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=True),
        sa.Column("apply_scope", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("video_species_id", sa.Integer(), sa.ForeignKey("video_species.id"), nullable=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("video.id"), nullable=True),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("from_species_id", sa.Integer(), sa.ForeignKey("species.id"), nullable=True),
        sa.Column("to_species_id", sa.Integer(), sa.ForeignKey("species.id"), nullable=True),
        sa.Column("from_species_name", sa.String(length=128), nullable=True),
        sa.Column("to_species_name", sa.String(length=128), nullable=True),
        sa.Column("detection_provider", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("frames_json", sa.String(), nullable=True),
        sa.Column("crop_path", sa.String(length=1024), nullable=True),
        sa.Column("camera", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_feedback_event_created_at", "detection_feedback_event", ["created_at"])
    op.create_index(
        "ix_feedback_event_action_created_at",
        "detection_feedback_event",
        ["action", "created_at"],
    )
    op.create_index(
        "ix_feedback_event_video_species_id",
        "detection_feedback_event",
        ["video_species_id"],
    )
    op.create_index(
        "ix_feedback_event_video_track",
        "detection_feedback_event",
        ["video_id", "track_id"],
    )


def downgrade():
    pass
