"""Логирование, heartbeat, restart flag и пути записи процессора (#225)."""

import logging
import os
import threading
import time
from datetime import datetime, timezone

from api import API
from app_config.app_config import app_config
from motion_detectors.opencv_live_overlay import (
    refresh_all_opencv_live_detectors,
    snapshot_opencv_live_by_camera,
)
from processor_runtime_stats import flush_runtime_stats_snapshot, runtime_stats_snapshot

# last_video_ok_at / last_yolo_ok_at для статуса (обновляет main loop)
processor_status = {
    "last_video_ok_at": None,
    "last_yolo_ok_at": None,
    "last_yolo_detection_at": None,
}

_log = logging.getLogger(__name__)


def get_data_dir() -> str:
    """Каталог данных процессора (записи, логи, флаги). Совпадает с DATA_DIR в Docker."""
    return (os.environ.get("DATA_DIR") or "data").strip() or "data"


# MQTT-агрегатор для поля mqtt_connected в heartbeat (пишет main())
heartbeat_mqtt_ref = [None]


def _setup_logging():
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(fmt))
        root.addHandler(h)
    data_dir = get_data_dir()
    log_path = os.path.join(data_dir, "processor.log")
    try:
        from logging.handlers import RotatingFileHandler

        fh = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(fmt))
        root.addHandler(fh)
    except OSError as e:
        _log.warning("processor file logging disabled (%s): %s", log_path, e)


_setup_logging()


def get_output_path():
    """Каталог и логический путь для новой записи video.mp4."""
    data_dir = get_data_dir()
    subpath = time.strftime("%Y/%m/%d/%H%M%S")
    output_dir = os.path.join(data_dir, "recordings", subpath)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir, f"data/recordings/{subpath}"


def restart_flag_path():
    """Путь к флагу мягкого перезапуска процессора."""
    data_dir = get_data_dir()
    return os.path.join(data_dir, "restart_processor.flag")


def check_restart_flag():
    """If flag exists, exit so docker restarts the container."""
    flag_path = restart_flag_path()
    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
        except OSError as e:
            _log.debug("restart flag removal failed path=%s: %s", flag_path, e, exc_info=True)
        logging.info("Restart flag found, exiting for restart")
        raise SystemExit(0)


def heartbeat():
    """Периодический heartbeat в API (60 с)."""
    hb_row_id = None
    api = None
    while True:
        try:
            if api is None:
                api = API()
            data = {"status": "up"}
            if processor_status.get("last_video_ok_at"):
                data["last_video_ok_at"] = processor_status["last_video_ok_at"]
            if processor_status.get("last_yolo_ok_at"):
                data["last_yolo_ok_at"] = processor_status["last_yolo_ok_at"]
            if processor_status.get("last_yolo_detection_at"):
                data["last_yolo_detection_at"] = processor_status["last_yolo_detection_at"]
            ref = heartbeat_mqtt_ref[0] if heartbeat_mqtt_ref else None
            if ref is not None:
                try:
                    data["mqtt_connected"] = ref.is_mqtt_ok_for_heartbeat()
                except Exception:
                    data["mqtt_connected"] = False
            try:
                from encoding_status import get_last_encoding_used

                enc = get_last_encoding_used()
                if enc:
                    data["encoding_used"] = enc
            except Exception:
                _log.debug("heartbeat: encoding_status unavailable", exc_info=True)
            try:
                flush_runtime_stats_snapshot()
                data["runtime_stats"] = runtime_stats_snapshot()
            except Exception:
                _log.debug("heartbeat: runtime_stats flush/snapshot failed", exc_info=True)
            hb_row_id = api.activity_log(type="heartbeat", data=data, id=hb_row_id)
        except Exception as e:
            logging.error("Heartbeat failed: %s (will retry in 60s)", e)
        # Restart: только основной цикл (check_restart_flag); SystemExit из потока
        # не завершает процесс — см. PR #237 review.
        time.sleep(60)


def start_heartbeat_daemon():
    """Запустить поток heartbeat в фоне."""
    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()
    return t


_opencv_overlay_row_id = None
_opencv_overlay_empty_since: float | None = None


def _opencv_overlay_heartbeat_loop():
    """Публикует live-контуры OpenCV для UI в near-realtime."""
    global _opencv_overlay_row_id, _opencv_overlay_empty_since
    api = None
    try:
        tick_sec = float(app_config.get("ui.live_overlay_tick_seconds") or 0.12)
    except (TypeError, ValueError):
        tick_sec = 0.12
    tick_sec = min(0.5, max(0.05, tick_sec))
    while True:
        try:
            refresh_all_opencv_live_detectors()
            snap = snapshot_opencv_live_by_camera()
            if snap:
                _opencv_overlay_empty_since = None
                if api is None:
                    api = API()
                payload = {
                    "by_camera": snap,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
                _opencv_overlay_row_id = api.activity_log(
                    type="opencv_live",
                    data=payload,
                    id=_opencv_overlay_row_id,
                )
            else:
                now = time.time()
                if _opencv_overlay_empty_since is None:
                    _opencv_overlay_empty_since = now
                elif now - _opencv_overlay_empty_since >= 45:
                    logging.warning(
                        "OpenCV live overlay snapshot empty for %.0fs "
                        "(processor not analyzing frames?)",
                        now - _opencv_overlay_empty_since,
                    )
                    _opencv_overlay_empty_since = now
        except Exception as e:
            logging.error("OpenCV overlay heartbeat failed: %s (retry in %.2fs)", e, tick_sec)
        time.sleep(tick_sec)


def start_opencv_overlay_daemon():
    """Фоновая публикация opencv_live в activity_log для Live-оверлея."""
    t = threading.Thread(target=_opencv_overlay_heartbeat_loop, daemon=True)
    t.start()
    return t
