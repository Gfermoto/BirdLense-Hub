"""Тестовый прогон video.source=file без рестарта: desired.json + status.json (#270)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app_config.app_config import app_config
from file_test_paths import scan_video_files_in_dir
from processor_support import get_data_dir
from sources.video_file_source import FileTestIdleSource, VideoFileSource, VideoPlaylistSource

logger = logging.getLogger(__name__)

CONTROL_SUBDIR = "file_test_control"
DESIRED_NAME = "desired.json"
STATUS_NAME = "status.json"


def file_test_control_dir() -> str:
    return os.path.join(get_data_dir(), CONTROL_SUBDIR)


def ensure_file_test_control_dir() -> str:
    d = file_test_control_dir()
    os.makedirs(d, mode=0o755, exist_ok=True)
    return d


def resolved_file_dir_for_config() -> str:
    raw = (app_config.get("video.file_dir") or "/app/data/file_test").strip()
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    return os.path.normpath(os.path.join(get_data_dir(), raw.lstrip("./\\")))


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


def _effective_loop(loop_override: bool | None) -> bool:
    if loop_override is not None:
        return bool(loop_override)
    return bool(app_config.get("video.file_loop", False))


def _build_playlist_source(paths: list[str], *, loop: bool, main_size: tuple, lores_size: tuple) -> VideoPlaylistSource:
    realtime_sim = bool(app_config.get("video.file_realtime_simulation", False))
    rcodec = (app_config.get("video.record_stream_codec") or "h264").strip().lower()
    if rcodec not in ("h264", "copy"):
        rcodec = "h264"
    return VideoPlaylistSource(
        paths,
        main_size=main_size,
        lores_size=lores_size,
        loop=loop,
        advance_on_start=False,
        split_session_per_file=True,
        realtime_simulation=realtime_sim,
        record_stream_codec=rcodec,
    )


@dataclass
class FileTestRuntime:
    """Читает desired.json, переключает источник, пишет status.json."""

    media_source_ref: list[Any]
    media_setup: Any
    args: Any
    main_size: tuple[int, ...]
    lores_size: tuple[int, ...]
    armed: bool = True
    abort_session: bool = False
    loop_override: bool | None = None
    _last_desired_mtime: float = field(default=0.0, repr=False)
    _last_poll_during_session_monotonic: float = field(default=0.0, repr=False)
    phase: str = "idle"
    last_error: str | None = None
    frame_in_clip: int = 0

    def poll(self) -> None:
        ensure_file_test_control_dir()
        dpath = os.path.join(file_test_control_dir(), DESIRED_NAME)
        if os.path.isfile(dpath):
            try:
                mtime = os.path.getmtime(dpath)
                if mtime != self._last_desired_mtime:
                    self._last_desired_mtime = mtime
                    with open(dpath, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        if "armed" in data:
                            self.armed = bool(data["armed"])
                        if "loop" in data:
                            self.loop_override = bool(data["loop"])
                        if data.get("abort"):
                            self.abort_session = True
                            data = {k: v for k, v in data.items() if k != "abort"}
                            atomic_write_json(dpath, data)
            except (OSError, TypeError, ValueError) as e:
                self.last_error = str(e)
                logger.warning("file_test desired.json read failed: %s", e)

        self._apply_media_state()
        self._write_status_file()

    def poll_during_active_session(self, *, min_interval_s: float = 0.35) -> None:
        """Вызывать из цикла кадров записи: иначе внешний run_motion_loop не делает poll() и status.json замирает (кадры в UI = 0)."""
        now = time.monotonic()
        if now - self._last_poll_during_session_monotonic < min_interval_s:
            return
        self._last_poll_during_session_monotonic = now
        self.poll()

    def _playlist_paths(self) -> list[str]:
        return scan_video_files_in_dir(resolved_file_dir_for_config())

    def _apply_media_state(self) -> None:
        file_path = (app_config.get("video.file_path") or "").strip()
        if file_path:
            return
        paths = self._playlist_paths()
        loop = _effective_loop(self.loop_override)
        cur = self.media_source_ref[0]

        if not self.armed:
            if not isinstance(cur, FileTestIdleSource):
                self._swap_idle()
            self.phase = "idle"
            return

        if not paths:
            self.last_error = "no_video_files"
            if not isinstance(cur, FileTestIdleSource):
                self._swap_idle()
            self.phase = "waiting_files"
            return

        self.last_error = None
        if isinstance(cur, FileTestIdleSource):
            self._swap_playlist(paths, loop)
            self.phase = "armed"
            return
        if isinstance(cur, VideoPlaylistSource):
            cur.loop = loop
            if list(cur.video_paths) != paths:
                self._swap_playlist(paths, loop)
            self.phase = "armed"
            return
        self._swap_playlist(paths, loop)
        self.phase = "armed"

    def _swap_idle(self) -> None:
        old = self.media_source_ref[0]
        try:
            old.close()
        except Exception as e:
            logger.debug("close old media: %s", e)
        idle = FileTestIdleSource(main_size=self.main_size, lores_size=self.lores_size)
        self.media_source_ref[0] = idle
        self.media_setup.media_source = idle

    def _swap_playlist(self, paths: list[str], loop: bool) -> None:
        old = self.media_source_ref[0]
        try:
            old.close()
        except Exception as e:
            logger.debug("close old media: %s", e)
        vf = _build_playlist_source(paths, loop=loop, main_size=self.main_size, lores_size=self.lores_size)
        self.media_source_ref[0] = vf
        self.media_setup.media_source = vf

    def _write_status_file(self) -> None:
        src = self.media_source_ref[0]
        idx = 0
        total = 0
        current = ""
        loop_eff = _effective_loop(self.loop_override)
        if isinstance(src, VideoPlaylistSource):
            idx = int(src.video_index)
            total = len(src.video_paths)
            current = Path(str(src.video_path)).name if src.video_path else ""
            self.frame_in_clip = int(getattr(src, "frame_count", 0) or 0)
        elif isinstance(src, VideoFileSource):
            total = 1
            idx = 0
            current = Path(str(src.video_path)).name if src.video_path else ""
            self.frame_in_clip = int(getattr(src, "frame_count", 0) or 0)
        else:
            self.frame_in_clip = 0

        payload = {
            "armed": self.armed,
            "abort_pending": self.abort_session,
            "loop": loop_eff,
            "phase": self.phase,
            "current_file": current,
            "index": idx,
            "total": total,
            "frame_in_clip": self.frame_in_clip,
            "last_error": self.last_error,
            "file_dir": resolved_file_dir_for_config(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            atomic_write_json(os.path.join(file_test_control_dir(), STATUS_NAME), payload)
        except OSError as e:
            logger.warning("file_test status write failed: %s", e)

    def clear_abort_after_session(self) -> None:
        self.abort_session = False


def maybe_build_file_test_runtime(
    *,
    media_setup: Any,
    media_source_ref: list[Any],
    args: Any,
    main_size: tuple[int, ...],
    lores_size: tuple[int, ...],
) -> FileTestRuntime | None:
    if (app_config.get("video.source") or "").strip().lower() != "file":
        return None
    if args.input:
        return None
    if (app_config.get("video.file_path") or "").strip():
        return None

    paths = scan_video_files_in_dir(resolved_file_dir_for_config())
    armed = bool(paths)
    return FileTestRuntime(
        media_source_ref=media_source_ref,
        media_setup=media_setup,
        args=args,
        main_size=main_size,
        lores_size=lores_size,
        armed=armed,
        phase="armed" if armed else "idle",
    )
