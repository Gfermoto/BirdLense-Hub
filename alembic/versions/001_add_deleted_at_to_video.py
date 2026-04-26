"""Add Video.deleted_at for soft-delete marker with retention.files_only.

Revision ID: 001
Revises: 
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('video') as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_video_deleted_at', ['deleted_at'], unique=False)


def downgrade():
    with op.batch_alter_table('video') as batch_op:
        batch_op.drop_index('ix_video_deleted_at')
        batch_op.drop_column('deleted_at')
