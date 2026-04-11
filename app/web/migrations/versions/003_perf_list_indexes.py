"""Индексы для overlap-запросов video / species_visit (overview, отчёты, #294).

Revision ID: 003_perf_list_indexes
Revises: 002_hazel_grouse_species
Create Date: 2026-04-11

"""
from alembic import op
from sqlalchemy import inspect

revision = '003_perf_list_indexes'
down_revision = '002_hazel_grouse_species'
branch_labels = None
depends_on = None


def _index_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {ix['name'] for ix in insp.get_indexes(table)}


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)

    video_ix = _index_names(insp, 'video')
    if 'ix_video_start_time' not in video_ix:
        op.create_index('ix_video_start_time', 'video', ['start_time'], unique=False)
    if 'ix_video_end_time' not in video_ix:
        op.create_index('ix_video_end_time', 'video', ['end_time'], unique=False)

    sv_ix = _index_names(insp, 'species_visit')
    if 'ix_speciesvisit_end_time' not in sv_ix:
        op.create_index(
            'ix_speciesvisit_end_time',
            'species_visit',
            ['end_time'],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    sv_ix = _index_names(insp, 'species_visit')
    if 'ix_speciesvisit_end_time' in sv_ix:
        op.drop_index('ix_speciesvisit_end_time', table_name='species_visit')
    video_ix = _index_names(insp, 'video')
    if 'ix_video_end_time' in video_ix:
        op.drop_index('ix_video_end_time', table_name='video')
    if 'ix_video_start_time' in video_ix:
        op.drop_index('ix_video_start_time', table_name='video')
