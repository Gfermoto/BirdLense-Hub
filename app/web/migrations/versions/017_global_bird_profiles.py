"""Add global Bird Profile entity and link to video_species.

Revision ID: 017_global_bird_profiles
Revises: 016_behavior_shadow_fields
Create Date: 2026-05-18 16:40:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "017_global_bird_profiles"
down_revision = "016_behavior_shadow_fields"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _column_names(table: str) -> set[str]:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(table: str) -> set[str]:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    tables = _table_names()
    if "bird_profiles" not in tables:
        op.create_table(
            "bird_profiles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("display_name", sa.String(length=96), nullable=False),
            sa.Column("species_id", sa.Integer(), nullable=True),
            sa.Column("avatar_url", sa.String(length=512), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["species_id"], ["species.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    idx = _index_names("bird_profiles")
    if "ix_bird_profiles_display_name" not in idx:
        op.create_index("ix_bird_profiles_display_name", "bird_profiles", ["display_name"], unique=False)
    if "ix_bird_profiles_species_id" not in idx:
        op.create_index("ix_bird_profiles_species_id", "bird_profiles", ["species_id"], unique=False)
    if "ix_bird_profiles_status" not in idx:
        op.create_index("ix_bird_profiles_status", "bird_profiles", ["status"], unique=False)

    cols = _column_names("video_species")
    if "bird_profile_id" not in cols and "video_species" in _table_names():
        with op.batch_alter_table("video_species") as batch:
            batch.add_column(sa.Column("bird_profile_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_video_species_bird_profile_id",
                "bird_profiles",
                ["bird_profile_id"],
                ["id"],
            )
            batch.create_index("ix_videospecies_bird_profile_id", ["bird_profile_id"], unique=False)


def downgrade() -> None:
    if "video_species" in _table_names() and "bird_profile_id" in _column_names("video_species"):
        with op.batch_alter_table("video_species") as batch:
            try:
                batch.drop_index("ix_videospecies_bird_profile_id")
            except Exception:
                pass
            try:
                batch.drop_constraint("fk_video_species_bird_profile_id", type_="foreignkey")
            except Exception:
                pass
            batch.drop_column("bird_profile_id")

    if "bird_profiles" in _table_names():
        idx = _index_names("bird_profiles")
        if "ix_bird_profiles_status" in idx:
            op.drop_index("ix_bird_profiles_status", table_name="bird_profiles")
        if "ix_bird_profiles_species_id" in idx:
            op.drop_index("ix_bird_profiles_species_id", table_name="bird_profiles")
        if "ix_bird_profiles_display_name" in idx:
            op.drop_index("ix_bird_profiles_display_name", table_name="bird_profiles")
        op.drop_table("bird_profiles")

