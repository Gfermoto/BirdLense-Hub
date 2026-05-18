"""Add indexes for analytics endpoint query patterns."""

from alembic import op
from sqlalchemy import inspect


revision = "014_analytics_perf_indexes"
down_revision = "013_analytics_aggregates"
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
    if _table_exists(insp, "video_species"):
        idx = _index_names(insp, "video_species")
        if "ix_videospecies_source_video_provider" not in idx:
            op.create_index(
                "ix_videospecies_source_video_provider",
                "video_species",
                ["source", "video_id", "detection_provider"],
                unique=False,
            )
        if "ix_videospecies_video_track" not in idx:
            op.create_index(
                "ix_videospecies_video_track",
                "video_species",
                ["video_id", "track_id"],
                unique=False,
            )


def downgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if _table_exists(insp, "video_species"):
        idx = _index_names(insp, "video_species")
        if "ix_videospecies_video_track" in idx:
            op.drop_index("ix_videospecies_video_track", table_name="video_species")
        if "ix_videospecies_source_video_provider" in idx:
            op.drop_index("ix_videospecies_source_video_provider", table_name="video_species")
