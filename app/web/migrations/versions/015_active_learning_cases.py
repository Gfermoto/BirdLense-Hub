"""active learning cases queue

Revision ID: 015_active_learning_cases
Revises: 014_analytics_perf_indexes
Create Date: 2026-05-18 12:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "015_active_learning_cases"
down_revision = "014_analytics_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if "active_learning_case" in insp.get_table_names():
        return
    op.create_table(
        "active_learning_case",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("video_id", sa.Integer(), nullable=True),
        sa.Column("video_species_id", sa.Integer(), nullable=True),
        sa.Column("camera_id", sa.String(length=64), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("blind_score", sa.Float(), nullable=True),
        sa.Column("fallback_ratio", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("payload_json", sa.String(), nullable=True),
        sa.Column("export_tag", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["video.id"]),
        sa.ForeignKeyConstraint(["video_species_id"], ["video_species.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_active_learning_case_created",
        "active_learning_case",
        [sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_active_learning_case_status_created",
        "active_learning_case",
        ["status", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_active_learning_case_reason_created",
        "active_learning_case",
        ["reason_code", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ux_active_learning_case_unique",
        "active_learning_case",
        ["video_species_id", "reason_code"],
        unique=True,
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if "active_learning_case" not in insp.get_table_names():
        return
    idx = {x["name"] for x in insp.get_indexes("active_learning_case")}
    if "ux_active_learning_case_unique" in idx:
        op.drop_index("ux_active_learning_case_unique", table_name="active_learning_case")
    if "ix_active_learning_case_reason_created" in idx:
        op.drop_index("ix_active_learning_case_reason_created", table_name="active_learning_case")
    if "ix_active_learning_case_status_created" in idx:
        op.drop_index("ix_active_learning_case_status_created", table_name="active_learning_case")
    if "ix_active_learning_case_created" in idx:
        op.drop_index("ix_active_learning_case_created", table_name="active_learning_case")
    op.drop_table("active_learning_case")
