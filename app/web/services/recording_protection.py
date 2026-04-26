"""Каталоги сессий с избранным: при ``retention.protect_favorites`` не трогать ни файлы, ни соседние ролики в той же папке (purge + retention)."""

from __future__ import annotations

import logging
import os

from app_config.app_config import app_config
from models import Video, db

_log = logging.getLogger(__name__)


def protected_favorite_session_dirs(rec_dir: str) -> set[str]:
    """Реальные пути ``…/recordings/YYYY/MM/DD/HHMMSS``, где есть не удалённое избранное."""
    if not bool(app_config.get("retention.protect_favorites", True)):
        return set()
    out: set[str] = set()
    try:
        rec_real = os.path.realpath(rec_dir)
        app_base = os.path.dirname(os.path.dirname(rec_dir))
        rows = (
            db.session.query(Video.video_path)
            .filter(Video.favorite.is_(True), Video.deleted_at.is_(None), Video.video_path.isnot(None))
            .all()
        )
        for (vp,) in rows:
            if not vp or not isinstance(vp, str):
                continue
            rel = os.path.normpath(os.path.dirname(vp)).replace("\\", "/")
            if not rel or rel.startswith(".."):
                continue
            try:
                session_dir = os.path.realpath(os.path.join(app_base, rel))
            except OSError:
                continue
            if session_dir == rec_real or session_dir.startswith(rec_real + os.sep):
                out.add(session_dir)
    except Exception as e:
        _log.warning("protected_favorite_session_dirs: %s", e)
    return out


def session_dir_for_video_path(rec_dir: str, video_path: str | None) -> str | None:
    """Каталог сессии для ``video_path`` (как join в purge/retention); ``None`` если не под ``rec_dir``."""
    if not video_path or not isinstance(video_path, str):
        return None
    rel = os.path.normpath(os.path.dirname(video_path)).replace("\\", "/")
    if not rel or rel.startswith(".."):
        return None
    try:
        rec_real = os.path.realpath(rec_dir)
        app_base = os.path.dirname(os.path.dirname(rec_dir))
        session_dir = os.path.realpath(os.path.join(app_base, rel))
    except OSError:
        return None
    if session_dir == rec_real or session_dir.startswith(rec_real + os.sep):
        return session_dir
    return None


def video_row_in_protected_session(rec_dir: str, video_path: str | None, protected: set[str]) -> bool:
    """Есть ли каталог сессии этого ролика среди защищённых (рядом с избранным)."""
    if not protected:
        return False
    sd = session_dir_for_video_path(rec_dir, video_path)
    return bool(sd and sd in protected)
