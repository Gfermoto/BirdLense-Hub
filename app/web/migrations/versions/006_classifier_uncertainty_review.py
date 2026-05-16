"""Persist classifier uncertainty review metadata on video detections.

Revision ID: 006_classifier_uncertainty_review
Revises: 005_video_deleted_at
Create Date: 2026-04-28

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "006_classifier_uncertainty_review"
down_revision = "005_video_deleted_at"
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {idx["name"] for idx in insp.get_indexes(table)}


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name
    insp = inspect(conn)
    cols = _column_names(insp, "video_species")
    add_cols = []
    if "classifier_entropy" not in cols:
        add_cols.append(sa.Column("classifier_entropy", sa.Float(), nullable=True))
    if "classifier_top1_top2_margin" not in cols:
        add_cols.append(sa.Column("classifier_top1_top2_margin", sa.Float(), nullable=True))
    if "classifier_needs_review" not in cols:
        add_cols.append(
            sa.Column(
                "classifier_needs_review",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    if "review_reason" not in cols:
        add_cols.append(sa.Column("review_reason", sa.String(64), nullable=True))

    if add_cols:
        if dialect == "sqlite":
            with op.batch_alter_table("video_species") as batch:
                for col in add_cols:
                    batch.add_column(col)
        else:
            for col in add_cols:
                op.add_column("video_species", col)
        insp = inspect(conn)

    idxs = _index_names(insp, "video_species")
    if "ix_videospecies_classifier_needs_review" not in idxs:
        op.create_index(
            "ix_videospecies_classifier_needs_review",
            "video_species",
            ["classifier_needs_review"],
        )


def downgrade():
    pass
