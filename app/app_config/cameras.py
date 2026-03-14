"""
Общая логика фильтрации камер из video.cameras.

Используется в web (ui_routes) и processor (main).
"""


def get_valid_cameras(cameras_config: list) -> list[dict]:
    """
    Возвращает список камер с непустым stream_name.

    Каждая камера: {id, stream_name, name}.
    """
    if not cameras_config:
        return []
    return [
        {
            'id': c.get('id') or c.get('stream_name', ''),
            'stream_name': (c.get('stream_name') or c.get('id') or '').strip(),
            'name': c.get('name') or c.get('id') or c.get('stream_name', ''),
        }
        for c in cameras_config
        if (c.get('stream_name') or '').strip()
    ]


def cameras_for_api(valid_cameras: list) -> list[dict]:
    """Формат для API: id, name, stream_url."""
    return [
        {
            'id': c['id'],
            'name': c['name'],
            'stream_url': f"/go2rtc/stream.html?src={c['stream_name']}",
        }
        for c in valid_cameras
    ]


def cameras_for_processor(valid_cameras: list) -> list[dict]:
    """Формат для processor: id, stream_name."""
    return [
        {'id': c['id'], 'stream_name': c['stream_name']}
        for c in valid_cameras
    ]
