"""DATA_DIR и безопасные пути к файлам и записям (#222, было в util.py)."""

from __future__ import annotations

import logging
import os


def _data_dir() -> str:
    """Return base data directory (recordings, saved images, etc.)."""
    return os.environ.get("DATA_DIR") or os.path.join(os.path.dirname(__file__), "..", "data")


def data_dir() -> str:
    """Expose base data directory (dataset paths, retention, etc.)."""
    return _data_dir()


def _path_is_under_data_dir(base: str, full: str) -> bool:
    """Return whether full is under base (block data_evil-style prefixes)."""
    try:
        return os.path.commonpath([base, full]) == base
    except ValueError:
        return False


def _resolved_path_under_data_dir(path: str) -> str | None:
    """Resolve to a real path under DATA_DIR; join relatives to DATA_DIR first."""
    if not path or not isinstance(path, str) or path != os.path.normpath(path):
        return None
    try:
        base = os.path.realpath(_data_dir())
        if os.path.isabs(path):
            full = os.path.realpath(path)
        else:
            full = os.path.realpath(os.path.join(base, path))
    except (OSError, ValueError):
        return None
    if not _path_is_under_data_dir(base, full):
        return None
    if full != base and not full.startswith(base + os.sep):
        return None
    return full


def _is_safe_image_path(path: str) -> bool:
    """Путь под DATA_DIR, файл существует. Защита от path traversal."""
    full = _resolved_path_under_data_dir(path)
    if not full:
        return False
    try:
        # lgtm[py/path-injection] realpath+commonpath+startswith(base+sep)
        return os.path.isfile(full)
    except OSError:
        return False


def read_safe_image_bytes(path: str | None) -> tuple[bytes | None, str | None]:
    """Прочитать файл только под DATA_DIR. (bytes, None) или (None, причина).

    Проверки realpath + commonpath + ``startswith(base + sep)`` и ФС —
    в одной функции (требование CodeQL py/path-injection).
    """
    full = _resolved_path_under_data_dir(path) if path else None
    if not full:
        return None, "unsafe_path"
    try:
        if not os.path.isfile(full):
            return None, "unsafe_path"
    except OSError:
        return None, "unsafe_path"
    try:
        # lgtm[py/path-injection] full только из _resolved_path_under_data_dir (realpath + commonpath).
        with open(full, "rb") as f:
            return f.read(), None
    except OSError as e:
        logging.warning("Cannot read safe image: %s", e)
        return None, "read_failed"


def remove_safe_image_file(path: str | None) -> None:
    """Удалить файл только если он под DATA_DIR (те же проверки, что для чтения)."""
    full = _resolved_path_under_data_dir(path) if path else None
    if not full:
        return
    try:
        if not os.path.isfile(full):
            return
    except OSError:
        return
    try:
        # lgtm[py/path-injection] full только из _resolved_path_under_data_dir (realpath + commonpath).
        os.remove(full)
    except OSError:
        pass


def recordings_dir():
    """Path to data/recordings directory."""
    return os.path.join(_data_dir(), "recordings")


def full_path_for_video(video_path: str) -> str | None:
    """Абсолютный путь к видеофайлу по значению из БД.

    Ожидается относительный путь ``data/recordings/YYYY/MM/...`` от родителя
    ``DATA_DIR``. Результат всегда строго внутри ``DATA_DIR``.
    """
    if not video_path or not isinstance(video_path, str):
        return None
    norm_vp = os.path.normpath(video_path)
    if os.path.isabs(norm_vp):
        return None
    if norm_vp.startswith(".." + os.sep) or norm_vp == "..":
        return None
    try:
        data_real = os.path.realpath(_data_dir())
        app_base = os.path.realpath(os.path.dirname(data_real))
        full = os.path.realpath(os.path.join(app_base, norm_vp))
    except (OSError, ValueError):
        return None
    if not _path_is_under_data_dir(data_real, full):
        return None
    if full != data_real and not full.startswith(data_real + os.sep):
        return None
    return full


def resolve_recording_video_file(video_path: str) -> str | None:
    """Абсолютный путь к mp4 для пересчёта треков и проверок на диске.

    1. Стандартное значение из БД ``data/recordings/.../video.mp4`` —
       через :func:`full_path_for_video`.
    2. Устаревший относительный путь от каталога ``recordings/`` (только
       ``YYYY/MM/DD/...``), если файл там действительно есть.
    """
    if not video_path or not isinstance(video_path, str):
        return None
    norm_vp = os.path.normpath(video_path.strip())
    if norm_vp.startswith(".." + os.sep) or norm_vp == "..":
        return None
    if os.path.isabs(norm_vp):
        return None

    primary = full_path_for_video(video_path)
    try:
        if primary and os.path.isfile(primary):
            return primary
    except OSError:
        pass

    data_prefix = "data" + os.sep + "recordings" + os.sep
    if norm_vp.startswith(data_prefix):
        return None

    try:
        rec = os.path.realpath(recordings_dir())
        cand = os.path.realpath(os.path.join(rec, norm_vp))
    except (OSError, ValueError):
        return None
    data_real = os.path.realpath(_data_dir())
    if not _path_is_under_data_dir(data_real, cand):
        return None
    if cand != rec and not cand.startswith(rec + os.sep):
        return None
    try:
        return cand if os.path.isfile(cand) else None
    except OSError:
        return None
