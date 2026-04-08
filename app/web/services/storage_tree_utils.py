"""Подсчёт файлов и размера дерева каталогов (диагностика / purge)."""
from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)


def get_tree_storage_info(dir_path: str) -> tuple[int, int]:
    """Число файлов и суммарный размер (байты) под ``dir_path``."""
    total_size = 0
    total_files = 0
    for root, _, files in os.walk(dir_path):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                total_size += os.path.getsize(file_path)
                total_files += 1
            except OSError as e:
                _log.error('Error getting size for %s: %s', file_path, e)
    return total_files, total_size
