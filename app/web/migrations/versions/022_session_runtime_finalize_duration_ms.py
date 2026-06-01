"""Add finalize duration column to session runtime metrics.

Revision ID: 022_session_runtime_finalize_duration_ms
Revises: 021_session_runtime_latency_columns
Create Date: 2026-06-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "022_session_runtime_finalize_duration_ms"
down_revision = "021_session_runtime_latency_columns"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    table_names = set(insp.get_table_names())
    if "session_runtime_metrics" not in table_names:
        return

    cols = {c["name"] for c in insp.get_columns("session_runtime_metrics")}
    if "finalize_duration_ms" not in cols:
        op.add_column(
            "session_runtime_metrics",
            sa.Column("finalize_duration_ms", sa.Float(), nullable=True),
        )


def downgrade():
    pass
