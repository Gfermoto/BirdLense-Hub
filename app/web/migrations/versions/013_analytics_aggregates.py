"""Add analytics aggregate tables for heatmap and visit timeseries."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "013_analytics_aggregates"
down_revision = "012_session_runtime_and_detector_health"
branch_labels = None
depends_on = None


def _table_exists(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _index_names(insp, table_name: str) -> set[str]:
    if not _table_exists(insp, table_name):
        return set()
    return {idx["name"] for idx in insp.get_indexes(table_name)}


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)

    if not _table_exists(insp, "analytics_heatmap_cell"):
        op.create_table(
            "analytics_heatmap_cell",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bucket_hour", sa.DateTime(timezone=True), nullable=False),
            sa.Column("camera_id", sa.String(length=64), nullable=True),
            sa.Column("grid_size", sa.Integer(), nullable=False, server_default="12"),
            sa.Column("cell_x", sa.Integer(), nullable=False),
            sa.Column("cell_y", sa.Integer(), nullable=False),
            sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    idx = _index_names(insp, "analytics_heatmap_cell")
    if "ix_analytics_heatmap_bucket" not in idx:
        op.create_index(
            "ix_analytics_heatmap_bucket",
            "analytics_heatmap_cell",
            ["bucket_hour", "camera_id", "grid_size"],
            unique=False,
        )
    if "ux_analytics_heatmap_cell" not in idx:
        op.create_index(
            "ux_analytics_heatmap_cell",
            "analytics_heatmap_cell",
            ["bucket_hour", "camera_id", "grid_size", "cell_x", "cell_y"],
            unique=True,
        )

    if not _table_exists(insp, "analytics_visit_hourly"):
        op.create_table(
            "analytics_visit_hourly",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bucket_hour", sa.DateTime(timezone=True), nullable=False),
            sa.Column("camera_id", sa.String(length=64), nullable=True),
            sa.Column("detections", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yolo_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("frigate_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("blind_confirmed_sessions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_confidence", sa.Float(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    idx2 = _index_names(insp, "analytics_visit_hourly")
    if "ux_analytics_visit_hourly_bucket" not in idx2:
        op.create_index(
            "ux_analytics_visit_hourly_bucket",
            "analytics_visit_hourly",
            ["bucket_hour", "camera_id"],
            unique=True,
        )
    if "ix_analytics_visit_hourly_bucket" not in idx2:
        op.create_index(
            "ix_analytics_visit_hourly_bucket",
            "analytics_visit_hourly",
            ["bucket_hour", "camera_id"],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if _table_exists(insp, "analytics_visit_hourly"):
        op.drop_index("ix_analytics_visit_hourly_bucket", table_name="analytics_visit_hourly")
        op.drop_index("ux_analytics_visit_hourly_bucket", table_name="analytics_visit_hourly")
        op.drop_table("analytics_visit_hourly")
    if _table_exists(insp, "analytics_heatmap_cell"):
        op.drop_index("ux_analytics_heatmap_cell", table_name="analytics_heatmap_cell")
        op.drop_index("ix_analytics_heatmap_bucket", table_name="analytics_heatmap_cell")
        op.drop_table("analytics_heatmap_cell")
