"""Encoding and capture backend normalisation for Orin (ONNX GPU).

Single source of truth — import from here, not inline copies.
"""

from __future__ import annotations

__all__ = ["normalize_video_encoding", "normalize_capture_backend"]

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
