"""Каталог: строка вида Hazel Grouse (рябчик) вне классов EU-классификатора.

Ручная разметка и резолвер имён; при ``species.catalog_strict_ingest: true``
авто-ингест строки «Hazel Grouse» с процессора по-прежнему уходит в Unknown,
пока класса нет в allowlist весов.

Revision ID: 002_hazel_grouse_species
Revises: 001_schema_patches
Create Date: 2026-04-08

"""
from alembic import op
import sqlalchemy as sa

revision = '002_hazel_grouse_species'
down_revision = '001_schema_patches'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM species WHERE name = 'Hazel Grouse' LIMIT 1")
    ).scalar()
    if exists:
        return
    row = conn.execute(
        sa.text(
            "SELECT id FROM species WHERE name = 'Grouse, Quail, and Allies' LIMIT 1"
        )
    ).fetchone()
    parent_id = int(row[0]) if row else None
    conn.execute(
        sa.text(
            """
            INSERT INTO species (
                name, parent_id, active, taxon_id,
                metadata_status, metadata_attempts
            ) VALUES (
                'Hazel Grouse', :parent_id, 1, NULL,
                'pending', 0
            )
            """
        ),
        {"parent_id": parent_id},
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM species
            WHERE name = 'Hazel Grouse'
              AND NOT EXISTS (
                SELECT 1 FROM video_species
                WHERE video_species.species_id = species.id
              )
            """
        )
    )
