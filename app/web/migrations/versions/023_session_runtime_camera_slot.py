"""Add camera_slot to session runtime metrics.

Revision ID: 023_session_runtime_camera_slot
Revises: 022_session_runtime_finalize_duration_ms
Create Date: 2026-06-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "023_session_runtime_camera_slot"
down_revision = "022_session_runtime_finalize_duration_ms"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    table_names = set(insp.get_table_names())
    if "session_runtime_metrics" not in table_names:
        return

    cols = {c["name"] for c in insp.get_columns("session_runtime_metrics")}
    if "camera_slot" not in cols:
        op.add_column(
            "session_runtime_metrics",
            sa.Column("camera_slot", sa.String(length=64), nullable=True),
        )

    idx = {i.get("name") for i in insp.get_indexes("session_runtime_metrics")}
    if "ix_session_runtime_metrics_slot_created" not in idx:
        op.create_index(
            "ix_session_runtime_metrics_slot_created",
            "session_runtime_metrics",
            ["camera_slot", "created_at"],
        )


def downgrade():
    pass
