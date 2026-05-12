"""
Общая логика фильтрации камер из video.cameras.

Используется в web (например ui_status_push_routes, status_service) и processor (main).
"""


def get_valid_cameras(cameras_config: list) -> list[dict]:
    """
    Возвращает список камер с непустым stream_name.

    Каждая камера: {id, stream_name, name, detect_stream_name?}.
    ``detect_stream_name`` — второй поток Go2RTC для motion/YOLO (как detect в Frigate);
    запись по-прежнему с ``stream_name`` (main).
    """
    if not cameras_config:
        return []
    out: list[dict] = []
    for c in cameras_config:
        sn = (c.get('stream_name') or '').strip()
        if not sn:
            continue
        dsn = (c.get('detect_stream_name') or '').strip()
        row = {
            'id': c.get('id') or sn,
            'stream_name': sn,
            'name': c.get('name') or c.get('id') or sn,
        }
        if dsn:
            row['detect_stream_name'] = dsn
        out.append(row)
    return out


def cameras_for_api(valid_cameras: list) -> list[dict]:
    """Формат для API: id, name, stream_url, stream_url_mjpeg (fallback от процессора)."""
    return [
        {
            'id': c['id'],
            'name': c['name'],
            'stream_url': f"/go2rtc/stream.html?src={c['stream_name']}",
            'stream_url_mjpeg': f"/processor/live/{i}",
        }
        for i, c in enumerate(valid_cameras)
    ]


def cameras_for_processor(valid_cameras: list) -> list[dict]:
    """Формат для processor: id, stream_name, optional detect_stream_name."""
    rows: list[dict] = []
    for c in valid_cameras:
        row = {'id': c['id'], 'stream_name': c['stream_name']}
        dsn = (c.get('detect_stream_name') or '').strip()
        if dsn:
            row['detect_stream_name'] = dsn
        rows.append(row)
    return rows
