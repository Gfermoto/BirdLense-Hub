"""Логирование, heartbeat, restart flag и пути записи процессора (#225)."""

import logging
import os
import threading
import time

from api import API

# last_video_ok_at / last_yolo_ok_at для статуса (обновляет main loop)
processor_status = {'last_video_ok_at': None, 'last_yolo_ok_at': None}

# MQTT-агрегатор для поля mqtt_connected в heartbeat (пишет main())
heartbeat_mqtt_ref = [None]


def _setup_logging():
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(fmt))
        root.addHandler(h)
    data_dir = os.environ.get('DATA_DIR', 'data')
    log_path = os.path.join(data_dir, 'processor.log')
    try:
        from logging.handlers import RotatingFileHandler

        fh = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=2,
            encoding='utf-8',
        )
        fh.setFormatter(logging.Formatter(fmt))
        root.addHandler(fh)
    except OSError:
        pass


_setup_logging()


def get_output_path():
    """Каталог и логический путь для новой записи video.mp4."""
    data_dir = os.environ.get('DATA_DIR', 'data')
    subpath = time.strftime('%Y/%m/%d/%H%M%S')
    output_dir = os.path.join(data_dir, 'recordings', subpath)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir, f'data/recordings/{subpath}'


def restart_flag_path():
    """Путь к флагу мягкого перезапуска процессора."""
    data_dir = os.environ.get('DATA_DIR', 'data')
    return os.path.join(data_dir, 'restart_processor.flag')


def check_restart_flag():
    """If flag exists, exit so docker restarts the container."""
    flag_path = restart_flag_path()
    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
        except OSError:
            pass
        logging.info('Restart flag found, exiting for restart')
        raise SystemExit(0)


def heartbeat():
    """Периодический heartbeat в API (60 с)."""
    hb_row_id = None
    api = None
    while True:
        try:
            if api is None:
                api = API()
            data = {'status': 'up'}
            if processor_status.get('last_video_ok_at'):
                data['last_video_ok_at'] = processor_status['last_video_ok_at']
            if processor_status.get('last_yolo_ok_at'):
                data['last_yolo_ok_at'] = processor_status['last_yolo_ok_at']
            ref = heartbeat_mqtt_ref[0] if heartbeat_mqtt_ref else None
            if ref is not None:
                try:
                    data['mqtt_connected'] = ref.is_mqtt_ok_for_heartbeat()
                except Exception:
                    data['mqtt_connected'] = False
            try:
                from encoding_status import get_last_encoding_used

                enc = get_last_encoding_used()
                if enc:
                    data['encoding_used'] = enc
            except Exception:
                pass
            hb_row_id = api.activity_log(
                type='heartbeat', data=data, id=hb_row_id
            )
        except Exception as e:
            logging.error('Heartbeat failed: %s (will retry in 60s)', e)
        check_restart_flag()
        time.sleep(60)


def start_heartbeat_daemon():
    """Запустить поток heartbeat в фоне."""
    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()
    return t
