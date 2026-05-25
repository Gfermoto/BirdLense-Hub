"""
Общая логика фильтрации камер из video.cameras.

Используется в web (например ui_status_push_routes, status_service) и processor (main).
"""


def get_valid_cameras(cameras_config: list) -> list[dict]:
    """
    Возвращает список камер с непустым stream_name.

    Каждая камера: {id, stream_name, name, detect_stream_name?, opencv_masks?}.
    ``detect_stream_name`` — второй поток Go2RTC для motion/YOLO (как detect в Frigate);
    ``opencv_masks`` — Frigate-style полигоны для OpenCV-триггера на этой камере.
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
        masks = c.get('opencv_masks')
        if masks:
            row['opencv_masks'] = masks
        out.append(row)
    return out


def cameras_for_api(valid_cameras: list) -> list[dict]:
    """Формат для API: id, name, stream_url, stream_url_mjpeg, go2rtc_src (имя потока в Go2RTC)."""
    return [
        {
            'id': c['id'],
            'name': c['name'],
            'stream_url': f"/go2rtc/stream.html?src={c['stream_name']}",
            'go2rtc_src': c['stream_name'],
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
        masks = c.get('opencv_masks')
        if masks:
            row['opencv_masks'] = masks
        rows.append(row)
    return rows
