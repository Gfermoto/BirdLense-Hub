"""Идемпотентные колонки (раньше try/except ALTER в app.py).

Revision ID: 001_schema_patches
Revises:
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '001_schema_patches'
down_revision = None
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set:
    if table not in insp.get_table_names():
        return set()
    return {c['name'] for c in insp.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    def names(table):
        return _column_names(inspect(conn), table)

    # --- video_species ---
    vs_cols = []
    if 'detection_provider' not in names('video_species'):
        vs_cols.append(sa.Column('detection_provider', sa.String(), nullable=True))
    if 'manually_corrected' not in names('video_species'):
        vs_cols.append(sa.Column(
            'manually_corrected',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ))
    if vs_cols:
        if dialect == 'sqlite':
            with op.batch_alter_table('video_species') as batch:
                for c in vs_cols:
                    batch.add_column(c)
        else:
            for c in vs_cols:
                op.add_column('video_species', c)

    # --- species (без FK в SQLite — как прежний ALTER) ---
    sp_cols = []
    if 'taxon_id' not in names('species'):
        sp_cols.append(sa.Column('taxon_id', sa.Integer(), nullable=True))
    if 'metadata_status' not in names('species'):
        sp_cols.append(sa.Column(
            'metadata_status',
            sa.String(32),
            nullable=False,
            server_default='pending',
        ))
    if 'metadata_attempts' not in names('species'):
        sp_cols.append(sa.Column(
            'metadata_attempts',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ))
    if 'metadata_error' not in names('species'):
        sp_cols.append(sa.Column('metadata_error', sa.String(255), nullable=True))
    if 'metadata_source' not in names('species'):
        sp_cols.append(sa.Column('metadata_source', sa.String(64), nullable=True))
    if 'metadata_source_url' not in names('species'):
        sp_cols.append(sa.Column('metadata_source_url', sa.String(512), nullable=True))
    if 'metadata_updated_at' not in names('species'):
        sp_cols.append(sa.Column(
            'metadata_updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ))
    if sp_cols:
        if dialect == 'sqlite':
            with op.batch_alter_table('species') as batch:
                for c in sp_cols:
                    batch.add_column(c)
        else:
            for c in sp_cols:
                op.add_column('species', c)

    # --- video.scales_weight_delta_kg ---
    if 'scales_weight_delta_kg' not in names('video'):
        col = sa.Column('scales_weight_delta_kg', sa.Float(), nullable=True)
        if dialect == 'sqlite':
            with op.batch_alter_table('video') as batch:
                batch.add_column(col)
        else:
            op.add_column('video', col)


def downgrade():
    pass
