"""Pydantic models for merged BirdLense YAML config (SOTA-01 / #492).

Validates critical keys and types while allowing unknown fields via ``extra='allow'``
so legacy/user keys are not dropped. Full JSON Schema is exported for docs/tooling.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

_SCHEMA_DIR = Path(__file__).resolve().parent / "schema"


class _SectionBase(BaseModel):
    model_config = ConfigDict(extra="allow")


class GeneralConfig(_SectionBase):
    app_name: str | None = None
    session_idle_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    require_auth_for_video_stream: bool | None = None


class DetectionConfig(_SectionBase):
    min_confidence_to_store: float | None = Field(default=None, ge=0.0, le=1.0)
    dedup_window_seconds: int | None = Field(default=None, ge=0, le=86400)


class VideoConfig(_SectionBase):
    source: str | None = None
    video_width: int | None = Field(
        default=None,
        ge=0,
        le=7680,
        description="Legacy file-replay only; ignored unless force_recording_resolution is true",
    )
    video_height: int | None = Field(
        default=None,
        ge=0,
        le=4320,
        description="Legacy file-replay only; ignored unless force_recording_resolution is true",
    )
    force_recording_resolution: bool | None = Field(
        default=None,
        description="When true, video_width/height override stream probe (legacy file-replay)",
    )
    detect_fps: float | None = Field(
        default=None,
        ge=0.0,
        le=120.0,
        description="0 = auto/probe from stream",
    )
    go2rtc_url: str | None = None


class SpeciesConfig(_SectionBase):
    catalog_allowlist_file: str | None = None
    catalog_strict_ingest: bool | None = None
    catalog_filter_off_allowlist: bool | None = None
    catalog_probe_audio_on_coverage: bool | None = None


class ProcessorConfig(_SectionBase):
    detection_strategy: Literal["two_stage"] | str | None = None
    inference_backend: Literal["torch", "openvino", "auto"] | str | None = None
    inference_device: str | None = None
    detection_device: str | None = None
    binary_imgsz: int | None = Field(default=None, ge=32, le=4096)
    min_confidence_binary: float | None = Field(default=None, ge=0.0, le=1.0)
    min_confidence_binary_bird: float | None = Field(default=None, ge=0.0, le=1.0)
    min_confidence_binary_rodent: float | None = Field(default=None, ge=0.0, le=1.0)
    bird_skip_classifier_max_area_frac: float | None = Field(
        default=None,
        ge=0.0,
        le=0.5,
        description="Skip classifier when generic Bird box area fraction exceeds threshold; 0 disables",
    )
    min_confidence_to_process: float | None = Field(default=None, ge=0.0, le=1.0)
    min_confidence_to_notify: float | None = Field(default=None, ge=0.0, le=1.0)
    min_track_duration: float | None = Field(default=None, ge=0.0, le=600.0)
    min_box_size_px: int | None = Field(default=None, ge=0, le=4096)
    max_record_seconds: int | None = Field(default=None, ge=1, le=86400)
    max_inactive_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)
    detect_use_native_resolution: bool | None = None
    inference_lores_px: int | None = Field(default=None, ge=32, le=4096)
    inference_lores_wh: list[int] | tuple[int, int] | None = None
    track_regen_lores_wh: list[int] | tuple[int, int] | None = None
    track_regen_frame_step: int | None = Field(default=None, ge=1, le=120)
    detection_quality_assumed_fps: float | None = Field(default=None, ge=0.0, le=120.0)
    openvino_binary_track_ultralytics_conf: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    openvino_binary_bird_score_scale: float | None = Field(default=None, ge=0.0, le=32.0)
    openvino_min_confidence_binary_bird: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    background_subtraction_enabled: bool | None = None
    background_subtraction_history: int | None = Field(default=None, ge=1, le=10000)
    background_subtraction_var_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=256.0,
    )
    background_subtraction_min_fg_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    background_subtraction_warmup_frames: int | None = Field(default=None, ge=0, le=10000)
    background_subtraction_detect_shadows: bool | None = None
    static_object_suppression_enabled: bool | None = None
    static_scene_bird_min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    static_temporal_max_jitter_px: float | None = Field(default=None, ge=0.0, le=64.0)
    scoring_engine_enabled: bool | None = None

    @field_validator("inference_lores_wh", "track_regen_lores_wh", mode="before")
    @classmethod
    def _normalize_wh_pair(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and len(value) == 2:
            w, h = value
            return [int(w), int(h)]
        raise ValueError("expected [width, height] with two positive integers")

    @model_validator(mode="after")
    def _wh_positive(self) -> ProcessorConfig:
        for name in ("inference_lores_wh", "track_regen_lores_wh"):
            pair = getattr(self, name)
            if pair is None:
                continue
            w, h = int(pair[0]), int(pair[1])
            if w < 1 or h < 1:
                raise ValueError(f"{name} width/height must be >= 1")
        return self


class MqttConfig(_SectionBase):
    broker: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)


class BirdlenseMergedConfig(BaseModel):
    """Top-level merged config (default + user)."""

    model_config = ConfigDict(extra="allow")

    general: GeneralConfig | None = None
    detection: DetectionConfig | None = None
    video: VideoConfig | None = None
    processor: ProcessorConfig | None = None
    species: SpeciesConfig | None = None
    mqtt: MqttConfig | None = None

    @model_validator(mode="after")
    def _store_le_process(self) -> BirdlenseMergedConfig:
        if self.detection is None or self.processor is None:
            return self
        store = self.detection.min_confidence_to_store
        proc = self.processor.min_confidence_to_process
        if store is not None and proc is not None and store > proc + 1e-9:
            raise ValueError(
                "detection.min_confidence_to_store (%s) must be <= "
                "processor.min_confidence_to_process (%s)" % (store, proc),
            )
        return self


def _pydantic_validate_enabled() -> bool:
    import os

    raw = (os.environ.get("BIRDLENSE_PYDANTIC_CONFIG_VALIDATE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def format_pydantic_issues(exc: ValidationError) -> list[str]:
    out: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "invalid")
        if loc:
            out.append("%s: %s" % (loc, msg))
        else:
            out.append(str(msg))
    return out


def validate_merged_config_pydantic(merged: dict) -> list[str]:
    """Validate merged config dict; return human-readable issue messages."""
    if not _pydantic_validate_enabled():
        return []
    if not isinstance(merged, dict):
        return ["config root must be a mapping (dict)"]
    try:
        BirdlenseMergedConfig.model_validate(merged)
        return []
    except ValidationError as exc:
        return format_pydantic_issues(exc)


def birdlense_config_json_schema() -> dict[str, Any]:
    """JSON Schema for documented sections (OpenAPI-adjacent tooling)."""
    return BirdlenseMergedConfig.model_json_schema(mode="validation")


def write_config_json_schema(path: Path | None = None) -> Path:
    """Write ``birdlense_config.schema.json`` next to package schema dir."""
    dest = path or (_SCHEMA_DIR / "birdlense_config.schema.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = birdlense_config_json_schema()
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


__all__ = [
    "BirdlenseMergedConfig",
    "DetectionConfig",
    "GeneralConfig",
    "ProcessorConfig",
    "SpeciesConfig",
    "VideoConfig",
    "birdlense_config_json_schema",
    "format_pydantic_issues",
    "validate_merged_config_pydantic",
    "write_config_json_schema",
]
