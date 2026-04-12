"""Таблица birdnet_fifo_event — персистентная очередь BirdNET MQTT (#269).

Revision ID: 004_birdnet_fifo_event
Revises: 003_perf_list_indexes
Create Date: 2026-04-12

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "004_birdnet_fifo_event"
down_revision = "003_perf_list_indexes"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if "birdnet_fifo_event" in insp.get_table_names():
        return
    op.create_table(
        "birdnet_fifo_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts_epoch", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_birdnet_fifo_event_ts_epoch",
        "birdnet_fifo_event",
        ["ts_epoch"],
        unique=False,
    )


def downgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if "birdnet_fifo_event" not in insp.get_table_names():
        return
    ix = {ix["name"] for ix in insp.get_indexes("birdnet_fifo_event")}
    if "ix_birdnet_fifo_event_ts_epoch" in ix:
        op.drop_index("ix_birdnet_fifo_event_ts_epoch", table_name="birdnet_fifo_event")
    op.drop_table("birdnet_fifo_event")
