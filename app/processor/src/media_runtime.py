"""Источники видео: go2rtc (мультикамера + MJPEG) или файл (tech debt #201)."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from api import API
from app_config.app_config import app_config
from app_config.cameras import get_valid_cameras, validate_go2rtc_detect_streams
from processor_support import check_restart_flag
from file_test_paths import scan_video_files_in_dir
from sources.go2rtc_stream_source import Go2RTCStreamSource, _build_stream_url
from sources.video_file_source import FileTestIdleSource, VideoFileSource, VideoPlaylistSource


@dataclass
class ProcessorMediaSetup:
    """Текущий media_source, фабрика по camera_id, кэш и список камер."""

    media_source: Any
    get_media_source: Callable[[Any], Any]
    media_sources_cache: Dict[Any, Any] = field(default_factory=dict)
    default_camera_id: Any = None
    cameras: List[Any] = field(default_factory=list)


def _wait_until_cameras_configured(api: API, cameras: list, go2rtc_url: str) -> None:
    if (not cameras or not go2rtc_url) and app_config.get("video.source") == "go2rtc":
        logging.warning(
            "video.cameras или video.go2rtc_url не заданы. Добавьте в Настройках. Processor будет ждать перезапуска.",
        )
        hb_id = None
        while True:
            check_restart_flag()
            try:
                hb_id = api.activity_log(
                    type="heartbeat",
                    data={"status": "waiting_cameras"},
                    id=hb_id,
                )
            except Exception as e:
                logging.error("Heartbeat (waiting_cameras) failed: %s", e)
            time.sleep(60)


def _start_mjpeg_feeder_thread(media_sources_cache: dict) -> None:
    def _mjpeg_feeder() -> None:
        while True:
            time.sleep(0.5)
            for _cid, src in list(media_sources_cache.items()):
                try:
                    if getattr(src, "push_one_frame_to_mjpeg", None):
                        src.push_one_frame_to_mjpeg()
                except Exception as e:
                    logging.debug("MJPEG feeder: %s", e)

    threading.Thread(target=_mjpeg_feeder, daemon=True).start()


def _resolve_capture_stream_url(
    *,
    go2rtc_url: str,
    detect_stream_name: str | None,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Resolve capture stream as direct URL or go2rtc stream name."""
    detect_sn = (detect_stream_name or "").strip()
    if not detect_sn:
        return None
    if "://" in detect_sn:
        return detect_sn
    return _build_stream_url(
        go2rtc_url,
        detect_sn,
        username=username,
        password=password,
    )


def _validate_go2rtc_detect_streams(cameras: list) -> None:
    """Every Go2RTC camera must have a separate detect substream (lores)."""
    issues = validate_go2rtc_detect_streams(cameras, video_source="go2rtc")
    if issues:
        raise RuntimeError("; ".join(issues))


def setup_processor_media(
    args: Any,
    main_size: tuple,
    lores_size: tuple,
    api: API,
) -> ProcessorMediaSetup:
    """Подготовить VideoFileSource или go2rtc + кэш потоков и фоновый MJPEG."""
    from app_config.cameras import cameras_for_processor, get_valid_cameras

    source = (app_config.get("video.source") or "go2rtc").strip().lower()
    video_config = app_config.get("video") or {}
    valid = get_valid_cameras(video_config=video_config)
    cameras = cameras_for_processor(valid)
    go2rtc_url = (os.environ.get("GO2RTC_URL") or app_config.get("video.go2rtc_url") or "").strip()

    if args.input:
        default_camera_id = cameras[0]["id"] if cameras else "default"
        vf = VideoFileSource(
            args.input,
            main_size=main_size,
            lores_size=lores_size,
        )
        return ProcessorMediaSetup(
            media_source=vf,
            get_media_source=lambda _cid: vf,
            media_sources_cache={},
            default_camera_id=default_camera_id,
            cameras=cameras,
        )

    if source == "file":
        file_path = (app_config.get("video.file_path") or "").strip()
        file_dir = (app_config.get("video.file_dir") or "/app/data/file_test").strip()
        realtime_sim = bool(app_config.get("video.file_realtime_simulation", False))
        rcodec = (app_config.get("video.record_stream_codec") or "h264").strip().lower()
        if rcodec not in ("h264", "copy"):
            rcodec = "h264"
        playlist_paths: list[str] = []
        if not file_path and file_dir:
            playlist_paths = scan_video_files_in_dir(file_dir)
        if not file_path:
            if not playlist_paths:
                logging.warning(
                    "video.source=file: в video.file_dir нет видео (%s). Режим ожидания (Hub → тестовый прогон или положите файлы).",
                    file_dir,
                )
                default_camera_id = cameras[0]["id"] if cameras else "default"
                idle = FileTestIdleSource(main_size=main_size, lores_size=lores_size)
                return ProcessorMediaSetup(
                    media_source=idle,
                    get_media_source=lambda _cid: idle,
                    media_sources_cache={},
                    default_camera_id=default_camera_id,
                    cameras=cameras,
                )
        default_camera_id = cameras[0]["id"] if cameras else "default"
        if file_path:
            vf = VideoFileSource(
                file_path,
                main_size=main_size,
                lores_size=lores_size,
                loop=bool(app_config.get("video.file_loop", False)),
                realtime_simulation=realtime_sim,
                record_stream_codec=rcodec,
            )
        else:
            vf = VideoPlaylistSource(
                playlist_paths,
                main_size=main_size,
                lores_size=lores_size,
                loop=bool(app_config.get("video.file_loop", False)),
                advance_on_start=False,
                split_session_per_file=True,
                realtime_simulation=realtime_sim,
                record_stream_codec=rcodec,
            )
        return ProcessorMediaSetup(
            media_source=vf,
            get_media_source=lambda _cid: vf,
            media_sources_cache={},
            default_camera_id=default_camera_id,
            cameras=cameras,
        )

    if not go2rtc_url:
        logging.warning(
            "video.go2rtc_url не задан. Укажите в Настройках: http://IP:1984",
        )

    _wait_until_cameras_configured(api, cameras, go2rtc_url)
    _validate_go2rtc_detect_streams(cameras)

    default_camera_id = cameras[0]["id"]
    media_sources_cache: Dict[Any, Any] = {}
    mjpeg_base_port = 8082

    def get_media_source(camera_id):
        if camera_id not in media_sources_cache:
            cam = next((c for c in cameras if c["id"] == camera_id), cameras[0])
            record_url = _build_stream_url(
                go2rtc_url,
                cam["stream_name"],
                username=app_config.get("video.go2rtc_username"),
                password=app_config.get("video.go2rtc_password"),
            )
            capture_url = _resolve_capture_stream_url(
                go2rtc_url=go2rtc_url,
                detect_stream_name=cam.get("detect_stream_name"),
                username=app_config.get("video.go2rtc_username"),
                password=app_config.get("video.go2rtc_password"),
            )
            if not capture_url:
                cid = str(cam.get("id") or "").strip() or "?"
                raise RuntimeError(
                    f"video.cameras: detect_stream_name required for camera {cid!r} "
                    "(lores motion/YOLO; main stream is record-only)"
                )
            idx = next(
                (i for i, c in enumerate(cameras) if c["id"] == camera_id),
                0,
            )
            encoding = (app_config.get("video.encoding") or "cpu").strip().lower()
            if encoding not in ("cpu", "intel"):
                encoding = "cpu"
            rcodec = (app_config.get("video.record_stream_codec") or "h264").strip().lower()
            if rcodec not in ("h264", "copy"):
                rcodec = "h264"
            capture_backend = (app_config.get("video.capture_backend") or "auto").strip().lower()
            if capture_backend not in ("auto", "opencv", "ffmpeg_vaapi"):
                capture_backend = "auto"
            rwv = app_config.get("video.record_with_vaapi")
            if rwv is None:
                record_with_vaapi = True
            elif isinstance(rwv, bool):
                record_with_vaapi = rwv
            else:
                s = str(rwv).strip().lower()
                record_with_vaapi = s not in ("0", "false", "no", "off")
            media_sources_cache[camera_id] = Go2RTCStreamSource(
                stream_url=record_url,
                main_size=main_size,
                lores_size=lores_size,
                auto_reconnect=app_config.get("video.auto_reconnect", True),
                mjpeg_port=mjpeg_base_port + idx,
                encoding_mode=encoding,
                record_stream_codec=rcodec,
                capture_backend=capture_backend,
                capture_stream_url=capture_url,
                record_with_vaapi=record_with_vaapi,
            )
        return media_sources_cache[camera_id]

    if source != "go2rtc":
        logging.warning("video.source=%s not supported, falling back to go2rtc", source)
    media_source = get_media_source(default_camera_id)
    for cam in cameras:
        get_media_source(cam["id"])

    _start_mjpeg_feeder_thread(media_sources_cache)

    return ProcessorMediaSetup(
        media_source=media_source,
        get_media_source=get_media_source,
        media_sources_cache=media_sources_cache,
        default_camera_id=default_camera_id,
        cameras=cameras,
    )
