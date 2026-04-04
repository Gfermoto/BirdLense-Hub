"""DATA_DIR, безопасные пути к файлам и разрешение путей к записям (#222 — вынесено из util.py)."""

from __future__ import annotations

import logging
import os


def _data_dir() -> str:
    """Base data directory (recordings, saved images, etc.)."""
    return os.environ.get('DATA_DIR') or os.path.join(
        os.path.dirname(__file__), '..', 'data'
    )


def data_dir() -> str:
    """Public access to base data directory. Use for dataset, retention, etc."""
    return _data_dir()


def _path_is_under_data_dir(base: str, full: str) -> bool:
    """Проверка вложенности без обхода через префикс-соседей (например data_evil при base=data)."""
    try:
        return os.path.commonpath([base, full]) == base
    except ValueError:
        return False


def _is_safe_image_path(path: str) -> bool:
    """Путь под DATA_DIR, файл существует. Защита от path traversal."""
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return False
    try:
        base = os.path.realpath(_data_dir())
        full = os.path.realpath(path)
    except (OSError, ValueError):
        return False
    if not _path_is_under_data_dir(base, full):
        return False
    # SafeAccessCheck: startswith в отдельном if (не внутри not (or …)) — иначе CodeQL не видит барьер.
    if full != base and not full.startswith(base + os.sep):
        return False
    try:
        return os.path.isfile(full)  # lgtm[py/path-injection] realpath+commonpath+startswith(base+sep)
    except OSError:
        return False


def read_safe_image_bytes(path: str | None) -> tuple[bytes | None, str | None]:
    """Прочитать файл только под DATA_DIR. (bytes, None) или (None, причина).

    Проверки realpath + commonpath + ``full.startswith(base + os.sep)`` и обращение к ФС —
    в одной функции (требование модели CodeQL py/path-injection).
    """
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return None, 'unsafe_path'
    try:
        base = os.path.realpath(_data_dir())
        full = os.path.realpath(path)
    except (OSError, ValueError):
        return None, 'unsafe_path'
    if not _path_is_under_data_dir(base, full):
        return None, 'unsafe_path'
    if full != base and not full.startswith(base + os.sep):
        return None, 'unsafe_path'
    try:
        if not os.path.isfile(full):  # lgtm[py/path-injection] validated under DATA_DIR
            return None, 'unsafe_path'
    except OSError:
        return None, 'unsafe_path'
    try:
        with open(full, 'rb') as f:  # lgtm[py/path-injection] validated under DATA_DIR
            return f.read(), None
    except OSError as e:
        logging.warning('Cannot read safe image: %s', e)
        return None, 'read_failed'


def remove_safe_image_file(path: str | None) -> None:
    """Удалить файл только если он под DATA_DIR (те же проверки, что для чтения)."""
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return
    try:
        base = os.path.realpath(_data_dir())
        full = os.path.realpath(path)
    except (OSError, ValueError):
        return
    if not _path_is_under_data_dir(base, full):
        return
    if full != base and not full.startswith(base + os.sep):
        return
    try:
        if not os.path.isfile(full):  # lgtm[py/path-injection] validated under DATA_DIR
            return
    except OSError:
        return
    try:
        os.remove(full)  # lgtm[py/path-injection] validated under DATA_DIR
    except OSError:
        pass


def recordings_dir():
    """Path to data/recordings directory."""
    return os.path.join(_data_dir(), 'recordings')


def full_path_for_video(video_path: str) -> str | None:
    """Полный путь по video_path из БД (data/recordings/YYYY/MM/DD/...)."""
    if not video_path:
        return None
    base = _data_dir()
    app_base = os.path.dirname(base)
    return os.path.normpath(os.path.join(app_base, video_path))
