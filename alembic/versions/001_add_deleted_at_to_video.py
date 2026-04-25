"""Add Video.deleted_at for soft-delete marker with retention.files_only.

Revision ID: 001
Revises: 
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('video', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_video_deleted_at', 'video', ['deleted_at'], unique=False)


def downgrade():
    op.drop_index('ix_video_deleted_at', table_name='video')
    op.drop_column('video', 'deleted_at')
