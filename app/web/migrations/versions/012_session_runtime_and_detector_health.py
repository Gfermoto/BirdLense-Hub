"""Add persistent processor runtime/session tables.

Revision ID: 012_session_runtime_and_detector_health
Revises: 011_video_behavior_recognition
Create Date: 2026-05-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "012_session_runtime_and_detector_health"
down_revision = "011_video_behavior_recognition"
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

    if not _table_exists(insp, "session_runtime_metrics"):
        op.create_table(
            "session_runtime_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("camera_id", sa.String(length=64), nullable=True),
            sa.Column("duration_s", sa.Float(), nullable=True),
            sa.Column("frames_seen", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yolo_frames_ran", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yolo_frames_with_tracks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yolo_frames_with_raw_boxes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yolo_raw_boxes_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yolo_accepted_boxes_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("low_light_blocked_frames", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("session_extended_by_frigate_only", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("bytetrack_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("post_fusion_persisted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rejected_decision_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mqtt_events_in_window", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yolo_blind_confirmed", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("runtime_profile", sa.String(length=32), nullable=True),
            sa.Column("video_file_ok", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("payload_json", sa.String(), nullable=True),
        )

    insp = inspect(conn)
    idx = _index_names(insp, "session_runtime_metrics")
    if "ix_session_runtime_metrics_camera_created" not in idx:
        op.create_index(
            "ix_session_runtime_metrics_camera_created",
            "session_runtime_metrics",
            ["camera_id", "created_at"],
        )
    if "ix_session_runtime_metrics_created" not in idx:
        op.create_index("ix_session_runtime_metrics_created", "session_runtime_metrics", ["created_at"])

    if not _table_exists(insp, "detector_health_events"):
        op.create_table(
            "detector_health_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("camera_id", sa.String(length=64), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
            sa.Column("details_json", sa.String(), nullable=True),
        )

    insp = inspect(conn)
    idx = _index_names(insp, "detector_health_events")
    if "ix_detector_health_events_camera_created" not in idx:
        op.create_index(
            "ix_detector_health_events_camera_created",
            "detector_health_events",
            ["camera_id", "created_at"],
        )
    if "ix_detector_health_events_type_created" not in idx:
        op.create_index(
            "ix_detector_health_events_type_created",
            "detector_health_events",
            ["event_type", "created_at"],
        )


def downgrade():
    pass
