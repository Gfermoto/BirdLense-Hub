"""Тестовый прогон video.source=file: список, upload, desired.json (#270)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app_config.app_config import app_config
from data_paths import _data_dir, _resolved_path_under_data_dir

logger = logging.getLogger(__name__)

CONTROL_SUBDIR = "file_test_control"
DESIRED_NAME = "desired.json"
STATUS_NAME = "status.json"

_VIDEO_GLOBS = ("*.mp4", "*.MP4", "*.mov", "*.MOV", "*.mkv", "*.MKV")
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def _control_dir() -> str:
    return os.path.join(_data_dir(), CONTROL_SUBDIR)


def _ensure_control_dir() -> None:
    os.makedirs(_control_dir(), mode=0o755, exist_ok=True)


def atomic_write_json(path: str, data: dict) -> None:
    d = os.path.dirname(path)
    os.makedirs(d, mode=0o755, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def resolved_file_test_dir() -> tuple[str | None, str | None]:
    """Абсолютный путь к video.file_dir под DATA_DIR или (None, error)."""
    raw = (app_config.get("video.file_dir") or "/app/data/file_test").strip()
    full = _resolved_path_under_data_dir(raw)
    if not full:
        return None, "invalid_file_dir"
    try:
        os.makedirs(full, mode=0o755, exist_ok=True)
    except OSError as e:
        return None, f"mkdir_failed:{e}"
    return full, None


def _safe_join_file(base: str, name: str) -> str | None:
    bn = os.path.basename(str(name).strip())
    if not bn or bn != str(name).strip() or bn in (".", ".."):
        return None
    cand = os.path.normpath(os.path.join(base, bn))
    try:
        cb = os.path.realpath(cand)
        br = os.path.realpath(base)
    except OSError:
        return None
    if cb == br or not cb.startswith(br + os.sep):
        return None
    return cb if os.path.isfile(cb) else None


def _ffprobe_duration(path: str) -> float | None:
    try:
        run = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if run.returncode != 0:
            return None
        s = (run.stdout or "").strip()
        if not s:
            return None
        return float(s)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None


def list_file_test_files() -> tuple[dict[str, Any], int]:
    base, err = resolved_file_test_dir()
    if err:
        return {"error": err}, 400
    items: list[dict[str, Any]] = []
    for pat in _VIDEO_GLOBS:
        for p in sorted(Path(base).glob(pat)):
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            items.append(
                {
                    "name": p.name,
                    "size": int(st.st_size),
                    "duration_sec": _ffprobe_duration(str(p)),
                }
            )
    items.sort(key=lambda x: x["name"].lower())
    return {"file_dir": base, "files": items}, 200


def read_processor_status() -> dict[str, Any] | None:
    sp = os.path.join(_control_dir(), STATUS_NAME)
    if not os.path.isfile(sp):
        return None
    try:
        with open(sp, encoding="utf-8") as f:
            out = json.load(f)
        return out if isinstance(out, dict) else None
    except (OSError, TypeError, ValueError):
        return None


def get_file_test_status() -> tuple[dict[str, Any], int]:
    base, err = resolved_file_test_dir()
    if err:
        return {"error": err}, 400
    desired_path = os.path.join(_control_dir(), DESIRED_NAME)
    desired: dict[str, Any] = {}
    if os.path.isfile(desired_path):
        try:
            with open(desired_path, encoding="utf-8") as f:
                desired = json.load(f)
            if not isinstance(desired, dict):
                desired = {}
        except (OSError, ValueError):
            desired = {}
    proc = read_processor_status()
    return {
        "file_dir": base,
        "desired": desired,
        "processor": proc,
        "config_loop_default": bool(app_config.get("video.file_loop", False)),
        "video_source": (app_config.get("video.source") or "").strip().lower(),
    }, 200


def write_desired(
    *,
    armed: bool | None = None,
    loop: bool | None = None,
    abort: bool = False,
) -> tuple[dict[str, Any], int]:
    _ensure_control_dir()
    path = os.path.join(_control_dir(), DESIRED_NAME)
    cur: dict[str, Any] = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                cur = json.load(f)
            if not isinstance(cur, dict):
                cur = {}
        except (OSError, ValueError):
            cur = {}
    if armed is not None:
        cur["armed"] = bool(armed)
    if loop is not None:
        cur["loop"] = bool(loop)
    if abort:
        cur["abort"] = True
    atomic_write_json(path, cur)
    return {"ok": True, "desired": cur}, 200


def delete_file_test_video(filename: str) -> tuple[dict[str, Any], int]:
    base, err = resolved_file_test_dir()
    if err:
        return {"error": err}, 400
    full = _safe_join_file(base, filename)
    if not full:
        return {"error": "not_found"}, 404
    try:
        os.remove(full)
    except OSError as e:
        logger.warning("file_test delete %s: %s", full, e)
        return {"error": "delete_failed"}, 500
    return {"ok": True}, 200


def save_file_test_upload(stream, filename: str | None) -> tuple[dict[str, Any], int]:
    """Сохранить werkzeug FileStorage в file_dir (размер ≤ MAX_UPLOAD_BYTES)."""
    from werkzeug.utils import secure_filename

    base, err = resolved_file_test_dir()
    if err:
        return {"error": err}, 400
    if not stream or not getattr(stream, "filename", None):
        return {"error": "no_file"}, 400
    raw_name = filename or stream.filename
    bn = secure_filename(str(raw_name))
    if not bn:
        return {"error": "invalid_name"}, 400
    suf = Path(bn).suffix
    if suf not in (".mp4", ".MP4", ".mov", ".MOV", ".mkv", ".MKV"):
        return {"error": "unsupported_type"}, 400
    dest = os.path.normpath(os.path.join(base, bn))
    try:
        dr = os.path.realpath(base)
        fr = os.path.realpath(dest)
    except OSError:
        return {"error": "path_error"}, 400
    if fr == dr or not fr.startswith(dr + os.sep):
        return {"error": "unsafe_path"}, 400
    total = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    return {"error": "file_too_large"}, 413
                out.write(chunk)
    except OSError as e:
        logger.warning("file_test upload save: %s", e)
        try:
            os.remove(dest)
        except OSError:
            pass
        return {"error": "save_failed"}, 500
    return {"ok": True, "name": bn}, 201
