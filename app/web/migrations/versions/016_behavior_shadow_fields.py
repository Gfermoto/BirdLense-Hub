"""Add behavior model and shadow fields on Video."""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


revision = "016_behavior_shadow_fields"
down_revision = "015_active_learning_cases"
branch_labels = None
depends_on = None


def _col_names(insp, table_name: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table_name)}


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if "video" not in insp.get_table_names():
        return
    cols = _col_names(insp, "video")
    if "behavior_model_kind" not in cols:
        op.add_column("video", sa.Column("behavior_model_kind", sa.String(length=32), nullable=True))
    if "behavior_model_version" not in cols:
        op.add_column("video", sa.Column("behavior_model_version", sa.String(length=96), nullable=True))
    if "behavior_shadow_label" not in cols:
        op.add_column("video", sa.Column("behavior_shadow_label", sa.String(length=32), nullable=True))
    if "behavior_shadow_confidence" not in cols:
        op.add_column("video", sa.Column("behavior_shadow_confidence", sa.Float(), nullable=True))
    if "behavior_shadow_model_kind" not in cols:
        op.add_column("video", sa.Column("behavior_shadow_model_kind", sa.String(length=32), nullable=True))
    if "behavior_shadow_model_version" not in cols:
        op.add_column("video", sa.Column("behavior_shadow_model_version", sa.String(length=96), nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if "video" not in insp.get_table_names():
        return
    cols = _col_names(insp, "video")
    for col in (
        "behavior_shadow_model_version",
        "behavior_shadow_model_kind",
        "behavior_shadow_confidence",
        "behavior_shadow_label",
        "behavior_model_version",
        "behavior_model_kind",
    ):
        if col in cols:
            op.drop_column("video", col)
