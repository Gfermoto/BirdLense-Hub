"""Жёсткая валидация путей записей/спектрограмм для ingest процессора.

Вынесено из data_paths. Модуль в paths-ignore CodeQL
(``.github/codeql/codeql-config-python.yml``): правило py/path-injection
не моделирует связку regex + full_path_for_video под DATA_DIR
(см. docs/SECURITY).
"""

from __future__ import annotations

import os
import re
from typing import Literal

from data_paths import full_path_for_video

RECORDING_VIDEO_PATH_RE = re.compile(
    r'^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/video\.mp4$'
)
RECORDING_SPECTROGRAM_PATH_RE = re.compile(
    r'^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/spectrogram_\d+\.jpg$'
)


def stat_recording_layout_file(
    logical_path: str,
    *,
    kind: Literal['video', 'spectrogram'],
) -> tuple[bool, str | None, str | None]:
    """Regex, full_path_for_video, затем проверка файла на диске."""
    is_video = kind == 'video'
    pat = RECORDING_VIDEO_PATH_RE if is_video else RECORDING_SPECTROGRAM_PATH_RE
    inv = 'video_path_invalid' if is_video else 'path_invalid'
    unr = 'video_path_unresolvable' if is_video else 'path_unresolvable'
    miss = 'video_file_missing' if is_video else 'file_missing'
    bad = 'video_file_unreadable' if is_video else 'file_unreadable'

    if not logical_path or not isinstance(logical_path, str):
        return False, None, inv
    lp = logical_path.strip()
    if not pat.match(lp):
        return False, None, inv
    full = full_path_for_video(lp)
    if not full:
        return False, None, unr
    try:
        if not os.path.isfile(full):
            return False, full, miss
        if os.path.getsize(full) <= 0:
            return False, full, bad
    except OSError:
        return False, full, bad
    return True, full, None
