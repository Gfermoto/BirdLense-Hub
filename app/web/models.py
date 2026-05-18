"""ORM-модели BirdLense: видео, детекции, визиты, каталог видов и вспомогательные сущности."""

import datetime
import uuid
from typing import List
from sqlalchemy import String, Integer, Float, DateTime, Table, ForeignKey, Column, Index, desc, JSON, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from flask_sqlalchemy import SQLAlchemy


class Base(DeclarativeBase):
    """Базовый класс SQLAlchemy 2.0 для всех таблиц Hub."""

    pass


db = SQLAlchemy(model_class=Base)


# Many-To-Many with additional columns
class VideoSpecies(db.Model):
    """Связь видео ↔ вид: интервалы, уверенность, провайдер детекции и трек."""

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("video.id"))
    species_id: Mapped[int] = mapped_column(Integer, ForeignKey("species.id"))
    species_visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("species_visit.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)  # seconds, relative to video.start_time
    end_time: Mapped[float] = mapped_column(Float, nullable=False)  # seconds, relative to video.start_time
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # video or audio
    detection_provider: Mapped[str] = mapped_column(String, nullable=True)  # yolo, frigate, birdnet_mqtt, legacy
    track_id: Mapped[int] = mapped_column(Integer, nullable=True)  # ByteTrack ID for stable identification
    bird_profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("bird_profiles.id"), nullable=True)
    # JSON: [{t: 0.1, bbox: [x1,y1,x2,y2]}, ...] for track visualization
    frames: Mapped[str] = mapped_column(String, nullable=True)
    classifier_entropy: Mapped[float | None] = mapped_column(Float, nullable=True)
    classifier_top1_top2_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    classifier_needs_review: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    review_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    individual_nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # True if user corrected species — track regen must not overwrite
    manually_corrected: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    video: Mapped["Video"] = relationship(back_populates="video_species")
    species: Mapped["Species"] = relationship(back_populates="video_species")
    species_visit: Mapped["SpeciesVisit"] = relationship(back_populates="video_species")
    bird_profile: Mapped["BirdProfile | None"] = relationship(back_populates="video_species")

    __table_args__ = (
        # improves both queries: created_at/species_id and just species_id
        Index("ix_videospecies_created_at_species", desc("created_at"), "species_id"),
        Index("ix_videospecies_species_created_at", "species_id", desc("created_at")),
        # for video details queries
        Index("ix_videospecies_video_id", "video_id"),
        Index("ix_videospecies_species_visit_id", "species_visit_id"),
    )


# Many-To-Many
video_bird_food_association = Table(
    "video_bird_food_association",
    Base.metadata,
    Column("video_id", Integer, ForeignKey("video.id"), primary_key=True),
    Column("birdfood_id", Integer, ForeignKey("bird_food.id"), primary_key=True),
)


class Species(db.Model):
    """Строка каталога видов в UI: иерархия, метаданные, привязка к каноническому taxon."""

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    taxon_id: Mapped[int] = mapped_column(Integer, ForeignKey("species_taxon.id"), nullable=True)
    parent_id = mapped_column(Integer, ForeignKey("species.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    image_url: Mapped[str] = mapped_column(String(), nullable=True)
    description: Mapped[str] = mapped_column(String(), nullable=True)
    metadata_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    metadata_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    metadata_error: Mapped[str] = mapped_column(String(255), nullable=True)
    metadata_source: Mapped[str] = mapped_column(String(64), nullable=True)
    metadata_source_url: Mapped[str] = mapped_column(String(512), nullable=True)
    metadata_updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    video_species: Mapped[List["VideoSpecies"]] = relationship(back_populates="species")
    children = relationship("Species", back_populates="parent")
    parent = relationship("Species", back_populates="children", remote_side=[id])
    species_visits: Mapped[List["SpeciesVisit"]] = relationship(back_populates="species")
    taxon: Mapped["SpeciesTaxon"] = relationship(back_populates="species")
    bird_profiles: Mapped[List["BirdProfile"]] = relationship(back_populates="species")

    __table_args__ = (
        Index("ix_species_parent_id", "parent_id"),
        Index("ix_species_taxon_id", "taxon_id"),
    )


class ReidTrainingPair(db.Model):
    """Operator feedback for ReID triplet mining (auto-link confirm/reject)."""

    __tablename__ = "reid_training_pairs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    anchor_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("bird_profiles.id", ondelete="SET NULL"), nullable=True
    )
    candidate_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("bird_profiles.id", ondelete="SET NULL"), nullable=True
    )
    anchor_video_species_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("video_species.id", ondelete="SET NULL"), nullable=True
    )
    candidate_video_species_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("video_species.id", ondelete="SET NULL"), nullable=True
    )
    similarity: Mapped[float | None] = mapped_column(nullable=True)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="auto_link_ui", server_default="auto_link_ui")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_reid_training_pairs_label", "label"),
        Index("ix_reid_training_pairs_created_at", "created_at"),
    )


class BirdProfile(db.Model):
    """Global bird identity profile for ReID and expert workflow."""

    __tablename__ = "bird_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(96), nullable=False)
    species_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("species.id"), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    species: Mapped["Species | None"] = relationship(back_populates="bird_profiles")
    video_species: Mapped[List["VideoSpecies"]] = relationship(back_populates="bird_profile")

    __table_args__ = (
        Index("ix_bird_profiles_display_name", "display_name"),
        Index("ix_bird_profiles_species_id", "species_id"),
        Index("ix_bird_profiles_status", "status"),
    )


class SpeciesTaxon(db.Model):
    """Canonical species record (single source of truth)."""

    id: Mapped[int] = mapped_column(primary_key=True)
    taxon_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    scientific_name: Mapped[str] = mapped_column(String(255), nullable=True)
    common_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    wiki_title: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    aliases: Mapped[List["SpeciesAlias"]] = relationship(back_populates="taxon", cascade="all, delete-orphan")
    species: Mapped[List["Species"]] = relationship(back_populates="taxon")

    __table_args__ = (
        Index("ix_species_taxon_common_name", "common_name"),
        Index("ix_species_taxon_taxon_key", "taxon_key"),
    )


class SpeciesAlias(db.Model):
    """Alias -> canonical taxon mapping."""

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    alias_key: Mapped[str] = mapped_column(String(255), nullable=False)
    taxon_id: Mapped[int] = mapped_column(Integer, ForeignKey("species_taxon.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    taxon: Mapped["SpeciesTaxon"] = relationship(back_populates="aliases")

    __table_args__ = (Index("ix_species_alias_alias_key", "alias_key"),)


class SpeciesUnresolvedName(db.Model):
    """Log unresolved species names for triage and quality gates."""

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        Index("ix_species_unresolved_normalized_key", "normalized_key"),
        Index("ix_species_unresolved_last_seen_at", desc("last_seen_at")),
    )


class BirdFood(db.Model):
    """Корм для настроек кормушки и связи many-to-many с видео."""

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(), nullable=True)
    image_url: Mapped[str] = mapped_column(String(), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    active: Mapped[bool] = mapped_column(nullable=False, default=False)


class Video(db.Model):
    """Запись ролика процессора: пути, погода, избранное, детекции и корм."""

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processor_version: Mapped[str] = mapped_column(nullable=False)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    video_path: Mapped[str] = mapped_column(nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        default=lambda: uuid.uuid4().hex,
    )
    ingest_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spectrogram_path: Mapped[str] = mapped_column(String, nullable=True)  # spectrogram image
    favorite: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Weather data
    weather_main: Mapped[str] = mapped_column(String(), nullable=True)  # short category, e.g., Rain
    weather_description: Mapped[str] = mapped_column(
        String(), nullable=True
    )  # long description, e.g., light intensity drizzle
    weather_temp: Mapped[int] = mapped_column(Float(precision=2), nullable=True)  # temperature in C
    weather_humidity: Mapped[int] = mapped_column(Integer(), nullable=True)  # humidity, %
    weather_pressure: Mapped[int] = mapped_column(
        Integer(), nullable=True
    )  # atmospheric pressure on the sea level, hPa
    weather_clouds: Mapped[int] = mapped_column(Integer(), nullable=True)  # cloudiness, %
    weather_wind_speed: Mapped[int] = mapped_column(Float(precision=2), nullable=True)  # wind speed, meter/sec
    # Оценка изменения массы на весах за интервал записи (кг), issue #167
    scales_weight_delta_kg: Mapped[float | None] = mapped_column(Float(precision=6), nullable=True)
    # Распознавание поведения: baseline из процессора (#416), nullable до первого включения.
    behavior_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    behavior_confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    behavior_model_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    behavior_model_version: Mapped[str | None] = mapped_column(String(96), nullable=True)
    behavior_shadow_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    behavior_shadow_confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    behavior_shadow_model_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    behavior_shadow_model_version: Mapped[str | None] = mapped_column(String(96), nullable=True)

    # Relations
    video_species: Mapped[List["VideoSpecies"]] = relationship(back_populates="video")
    food: Mapped[List[BirdFood]] = relationship(secondary=video_bird_food_association)

    __table_args__ = (
        # Hot paths: overview/report overlap on [start,end] vs day/window (#294).
        Index("ix_video_start_time", "start_time"),
        Index("ix_video_end_time", "end_time"),
        Index("ix_video_deleted_at", "deleted_at"),
        Index(
            "ux_video_idempotency_active",
            "idempotency_key",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class ActivityLog(db.Model):
    """Журнал событий UI/системы (тип + JSON payload)."""

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    data: Mapped[str] = mapped_column(String(), nullable=True)

    __table_args__ = (Index("ix_activitylog_type_created_at", "type", desc("created_at")),)


class DetectionFeedbackEvent(db.Model):
    """Operator correction/delete signals for feedback-learning loop (#397)."""

    __tablename__ = "detection_feedback_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # relabel | delete_as_background
    trigger_source: Mapped[str | None] = mapped_column(String(32), nullable=True)  # video | unknowns | ...
    apply_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    video_species_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("video_species.id"), nullable=True)
    video_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("video.id"), nullable=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    from_species_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("species.id"), nullable=True)
    to_species_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("species.id"), nullable=True)
    from_species_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    to_species_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    detection_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    frames_json: Mapped[str | None] = mapped_column(String, nullable=True)
    crop_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    camera: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_feedback_event_created_at", desc("created_at")),
        Index("ix_feedback_event_action_created_at", "action", desc("created_at")),
        Index("ix_feedback_event_video_species_id", "video_species_id"),
        Index("ix_feedback_event_video_track", "video_id", "track_id"),
    )


class SiteVisitor(db.Model):
    """Anonymous browser/day presence record for lightweight site visitor metrics."""

    __tablename__ = "site_visitor"

    id: Mapped[int] = mapped_column(primary_key=True)
    browser_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    seen_day: Mapped[str] = mapped_column(String(10), nullable=False)
    device_class: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_site_visitor_seen_day", "seen_day"),
        Index("ix_site_visitor_browser_hash", "browser_hash"),
        Index("ux_site_visitor_browser_day", "browser_hash", "seen_day", unique=True),
    )


class PushSubscription(db.Model):
    """Web Push subscription for browser notifications."""

    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(512), nullable=False)
    auth: Mapped[str] = mapped_column(String(256), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_pushsubscription_endpoint", "endpoint"),)


class BirdnetFifoEvent(db.Model):
    """Очередь нормализованных событий BirdNET MQTT: prior + UI; персистентность в SQLite (#269)."""

    __tablename__ = "birdnet_fifo_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_epoch: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (Index("ix_birdnet_fifo_event_ts_epoch", "ts_epoch"),)


class SessionRuntimeMetrics(db.Model):
    """Persistent runtime session summaries from processor (survives restarts)."""

    __tablename__ = "session_runtime_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    frames_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    yolo_frames_ran: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    yolo_frames_with_tracks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    yolo_frames_with_raw_boxes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    yolo_raw_boxes_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    yolo_accepted_boxes_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    low_light_blocked_frames: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    session_extended_by_frigate_only: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    bytetrack_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    post_fusion_persisted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rejected_decision_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mqtt_events_in_window: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    yolo_blind_confirmed: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    runtime_profile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    video_file_ok: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    payload_json: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_session_runtime_metrics_camera_created", "camera_id", desc("created_at")),
        Index("ix_session_runtime_metrics_created", desc("created_at")),
    )


class DetectorHealthEvent(db.Model):
    """Health/self-healing events for detector pipeline."""

    __tablename__ = "detector_health_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info", server_default="info")
    details_json: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_detector_health_events_camera_created", "camera_id", desc("created_at")),
        Index("ix_detector_health_events_type_created", "event_type", desc("created_at")),
    )


class AnalyticsHeatmapCell(db.Model):
    """Pre-aggregated heatmap cells for long windows."""

    __tablename__ = "analytics_heatmap_cell"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bucket_hour: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grid_size: Mapped[int] = mapped_column(Integer, nullable=False, default=12, server_default="12")
    cell_x: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_y: Mapped[int] = mapped_column(Integer, nullable=False)
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_analytics_heatmap_bucket", "bucket_hour", "camera_id", "grid_size"),
        Index("ux_analytics_heatmap_cell", "bucket_hour", "camera_id", "grid_size", "cell_x", "cell_y", unique=True),
    )


class AnalyticsVisitHourly(db.Model):
    """Hourly aggregates for visit quality trends."""

    __tablename__ = "analytics_visit_hourly"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bucket_hour: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detections: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    yolo_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    frigate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    blind_confirmed_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ux_analytics_visit_hourly_bucket", "bucket_hour", "camera_id", unique=True),
        Index("ix_analytics_visit_hourly_bucket", "bucket_hour", "camera_id"),
    )


class ActiveLearningCase(db.Model):
    """Hard-example queue for labelling and dataset export."""

    __tablename__ = "active_learning_case"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    video_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("video.id"), nullable=True)
    video_species_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("video_species.id"), nullable=True)
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    blind_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fallback_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    payload_json: Mapped[str | None] = mapped_column(String, nullable=True)
    export_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_active_learning_case_created", desc("created_at")),
        Index("ix_active_learning_case_status_created", "status", desc("created_at")),
        Index("ix_active_learning_case_reason_created", "reason_code", desc("created_at")),
        Index("ux_active_learning_case_unique", "video_species_id", "reason_code", unique=True),
    )


class SpeciesVisit(db.Model):
    """Represents a continuous period when a species species was present, groups video and audio detections"""

    id: Mapped[int] = mapped_column(primary_key=True)
    species_id: Mapped[int] = mapped_column(Integer, ForeignKey("species.id"), nullable=False)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_simultaneous: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # Max birds seen at once
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    species: Mapped["Species"] = relationship(back_populates="species_visits")
    video_species: Mapped[List["VideoSpecies"]] = relationship(back_populates="species_visit")

    __table_args__ = (
        Index("ix_speciesvisit_created_at_species", desc("start_time"), "species_id"),
        Index("ix_speciesvisit_species_created_at", "species_id", desc("start_time")),
        Index("ix_speciesvisit_end_time", "end_time"),
    )


class SystemResourceSample(db.Model):
    """Периодические снимки CPU/RAM/диск/GPU для графиков на странице «Система»."""

    __tablename__ = "system_resource_sample"

    id: Mapped[int] = mapped_column(primary_key=True)
    recorded_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (Index("ix_system_resource_sample_recorded_at", "recorded_at"),)
