"""Жёсткая валидация путей записей для ingest процессора.

Вынесено из data_paths. Модуль в paths-ignore CodeQL
(``.github/codeql/codeql-config-python.yml``): правило py/path-injection
не моделирует связку regex + full_path_for_video под DATA_DIR
(см. docs/SECURITY).
"""

from __future__ import annotations

import os
import re

from data_paths import full_path_for_video

RECORDING_VIDEO_PATH_RE = re.compile(r"^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/video\.mp4$")


def stat_recording_layout_file(
    logical_path: str,
) -> tuple[bool, str | None, str | None]:
    """Regex, full_path_for_video, затем проверка файла на диске."""
    if not logical_path or not isinstance(logical_path, str):
        return False, None, "video_path_invalid"
    lp = logical_path.strip()
    if not RECORDING_VIDEO_PATH_RE.match(lp):
        return False, None, "video_path_invalid"
    full = full_path_for_video(lp)
    if not full:
        return False, None, "video_path_unresolvable"
    try:
        if not os.path.isfile(full):
            return False, full, "video_file_missing"
        if os.path.getsize(full) <= 0:
            return False, full, "video_file_unreadable"
    except OSError:
        return False, full, "video_file_unreadable"
    return True, full, None
