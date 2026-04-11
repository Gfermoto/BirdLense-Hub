"""Хвост processor.log для GET /api/ui/system/logs (#293)."""
from __future__ import annotations

import os
from collections import deque

from util import recordings_dir

LOG_LINES_DEFAULT = 200
LOG_LINES_MAX = 500


def clamp_processor_log_line_count(raw) -> int:
    try:
        return max(1, min(int(raw), LOG_LINES_MAX))
    except (ValueError, TypeError):
        return LOG_LINES_DEFAULT


def read_processor_log_tail(lines: int) -> dict:
    """Возвращает dict с ключами lines и path."""
    data_dir = os.path.dirname(recordings_dir())
    log_path = os.path.join(data_dir, 'processor.log')
    if not os.path.isfile(log_path):
        return {'lines': [], 'path': log_path}
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        tail = deque(f, maxlen=lines)
    return {'lines': list(tail), 'path': log_path}
