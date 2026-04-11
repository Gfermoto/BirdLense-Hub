"""Запрос перезапуска processor через flag-файл (#293)."""
from __future__ import annotations

import os


def write_processor_restart_flag(data_dir: str) -> None:
    """
    Создать restart_processor.flag и обновить .startup_notify_skip в data_dir.

    Raises:
        OSError: не удалось создать каталог или файлы.
    """
    os.makedirs(data_dir, exist_ok=True)
    flag_path = os.path.join(data_dir, 'restart_processor.flag')
    notify_skip_path = os.path.join(data_dir, '.startup_notify_skip')
    with open(flag_path, 'w', encoding='utf-8') as f:
        f.write('1')
    with open(notify_skip_path, 'a', encoding='utf-8'):
        os.utime(notify_skip_path, None)
