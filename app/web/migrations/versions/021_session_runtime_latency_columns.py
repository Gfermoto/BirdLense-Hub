"""Add explicit session runtime latency columns.

Revision ID: 021_session_runtime_latency_columns
Revises: 020_video_trigger_source
Create Date: 2026-06-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "021_session_runtime_latency_columns"
down_revision = "020_video_trigger_source"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    table_names = set(insp.get_table_names())
    if "session_runtime_metrics" not in table_names:
        return

    cols = {c["name"] for c in insp.get_columns("session_runtime_metrics")}
    if "trigger_to_first_bbox_latency_s" not in cols:
        op.add_column(
            "session_runtime_metrics",
            sa.Column(
                "trigger_to_first_bbox_latency_s", sa.Float(), nullable=True
            ),
        )
    if "first_track_latency_s" not in cols:
        op.add_column(
            "session_runtime_metrics",
            sa.Column("first_track_latency_s", sa.Float(), nullable=True),
        )


def downgrade():
    pass
