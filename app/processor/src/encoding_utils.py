"""Encoding and capture backend normalisation for Orin (ONNX GPU).

Single source of truth — import from here, not inline copies.
"""

from __future__ import annotations

__all__ = [
    "normalize_video_encoding",
    "normalize_capture_backend",
    "parse_bool_config_flag",
    "resolve_record_hw_encode",
]

VALID_ENCODINGS: tuple[str, ...] = ("cpu", "jetson")
VALID_CAPTURE_BACKENDS: tuple[str, ...] = ("auto", "opencv", "ffmpeg_nvmpi")


def normalize_video_encoding(raw: str | None, default: str = "jetson") -> str:
    """Canonical video encoding: ``jetson`` (NVENC/NVDEC on Orin) or ``cpu``.

    Aliases ``orin``, ``nvenc``, ``nvmpi`` → ``jetson``.
    Unknown values fall back to *default*.
    """
    value = (raw or default).strip().lower()
    if value in ("orin", "nvenc", "nvmpi"):
        return "jetson"
    if value in VALID_ENCODINGS:
        return value
    return default


def normalize_capture_backend(raw: str | None, default: str = "auto") -> str:
    """Canonical capture backend.

    Valid: ``auto``, ``opencv``, ``ffmpeg_nvmpi`` (Orin NVDEC).
    Unknown values fall back to *default*.
    """
    value = (raw or default).strip().lower()
    if value in VALID_CAPTURE_BACKENDS:
        return value
    return default


def parse_bool_config_flag(value: object, *, default: bool = True) -> bool:
    """Parse YAML/bool-ish config flags (``0``, ``false``, ``off`` → False)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s not in ("0", "false", "no", "off")


def resolve_record_hw_encode(cfg: object) -> bool:
    """True → hardware MP4 encode (NVENC/GStreamer) when ``video.encoding=jetson``."""
    get = getattr(cfg, "get", None)
    if not callable(get):
        return True
    val = get("video.record_hw_encode")
    if val is None:
        val = get("video.record_with_vaapi")
    return parse_bool_config_flag(val, default=False)
