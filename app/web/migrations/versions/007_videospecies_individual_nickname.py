"""Add optional per-detection individual nickname field.

Revision ID: 007_videospecies_individual_nickname
Revises: 006_classifier_uncertainty_review
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "007_videospecies_individual_nickname"
down_revision = "006_classifier_uncertainty_review"
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name
    insp = inspect(conn)
    cols = _column_names(insp, "video_species")
    if "individual_nickname" in cols:
        return
    col = sa.Column("individual_nickname", sa.String(64), nullable=True)
    if dialect == "sqlite":
        with op.batch_alter_table("video_species") as batch:
            batch.add_column(col)
    else:
        op.add_column("video_species", col)


def downgrade():
    pass
