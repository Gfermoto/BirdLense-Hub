"""Сканирование видео в каталоге для video.source=file (issue #270)."""

from __future__ import annotations

from pathlib import Path

_VIDEO_GLOBS = ("*.mp4", "*.MP4", "*.mov", "*.MOV", "*.mkv", "*.MKV")


def scan_video_files_in_dir(file_dir: str) -> list[str]:
    """Отсортированный список путей к видео в каталоге (как в media_runtime)."""
    pdir = Path((file_dir or "").strip())
    if not pdir.is_dir():
        return []
    out: list[str] = []
    for ext in _VIDEO_GLOBS:
        out.extend(str(p) for p in sorted(pdir.glob(ext)))
    return out
