"""
Общая логика фильтрации камер из video.cameras.

Используется в web (например ui_status_push_routes, status_service) и processor (main).
"""


def _slot_key(value: object, *, idx: int) -> str:
    raw = str(value or "").strip()
    if not raw:
        return f"camera_{idx + 1}"
    if raw.isdigit():
        return f"camera_{int(raw)}"
    return raw


def _resolve_effective_cameras_from_video_config(video_config: dict | None) -> list[dict]:
    video_cfg = video_config or {}
    slots = video_cfg.get("camera_slots") or []
    profiles = video_cfg.get("camera_profiles") or {}
    bindings = video_cfg.get("camera_profile_bindings") or {}
    legacy_cameras = video_cfg.get("cameras") or []
    rows: list[dict] = []

    if isinstance(slots, list) and slots:
        for idx, slot in enumerate(slots):
            if not isinstance(slot, dict):
                continue
            slot_key = _slot_key(slot.get("slot"), idx=idx)
            profile_id = (
                str(
                    slot.get("profile")
                    or slot.get("profile_id")
                    or bindings.get(slot_key)
                    or "",
                ).strip()
                or None
            )
            profile = profiles.get(profile_id or "") if isinstance(profiles, dict) else None
            profile_dict = profile if isinstance(profile, dict) else {}
            merged: dict = dict(profile_dict)
            merged.update(slot)
            merged["camera_slot"] = slot_key
            if profile_id:
                merged["camera_profile"] = profile_id
            rows.append(merged)
        return rows

    # C2 dual-read compatibility: synthesize camera_slots from legacy video.cameras.
    for idx, cam in enumerate(legacy_cameras):
        if not isinstance(cam, dict):
            continue
        slot_key = _slot_key(cam.get("camera_slot"), idx=idx)
        row = dict(cam)
        row.setdefault("camera_slot", slot_key)
        if row.get("camera_profile"):
            row["camera_profile"] = str(row["camera_profile"]).strip()
        rows.append(row)
    return rows


def validate_go2rtc_detect_streams(
    valid_cameras: list,
    *,
    video_source: str | None = None,
) -> list[str]:
    """Issues when go2rtc live requires separate lores detect substream per camera."""
    source = (video_source or "go2rtc").strip().lower()
    if source != "go2rtc":
        return []
    issues: list[str] = []
    for c in valid_cameras:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or c.get("stream_name") or "?")
        sn = str(c.get("stream_name") or "").strip()
        dsn = str(c.get("detect_stream_name") or "").strip()
        if not dsn:
            issues.append(
                f"video.cameras[{cid}]: detect_stream_name required "
                "(lores motion/YOLO; stream_name is main record only)",
            )
            continue
        if dsn == sn:
            issues.append(
                f"video.cameras[{cid}]: detect_stream_name must differ from stream_name "
                "(main=record, detect=lores)",
            )
    return issues


def get_valid_cameras(
    cameras_config: list | None = None,
    *,
    video_config: dict | None = None,
) -> list[dict]:
    """
    Возвращает список камер с непустым stream_name.

    Каждая камера: {id, stream_name, name, detect_stream_name?, opencv_masks?}.
    ``detect_stream_name`` — обязателен при ``video.source=go2rtc``: lores motion/YOLO;
    ``stream_name`` — main, только запись FFmpeg.
    """
    source_rows: list = []
    if video_config is not None:
        source_rows = _resolve_effective_cameras_from_video_config(video_config)
    elif cameras_config:
        source_rows = cameras_config

    if not source_rows:
        return []
    out: list[dict] = []
    for idx, c in enumerate(source_rows):
        if not isinstance(c, dict):
            continue
        sn = (c.get('stream_name') or '').strip()
        if not sn:
            continue
        slot_key = _slot_key(c.get("camera_slot"), idx=idx)
        dsn = (c.get('detect_stream_name') or '').strip()
        legacy_id = str(c.get("id") or "").strip()
        row = {
            'id': sn,
            'stream_name': sn,
            'name': c.get('name') or legacy_id or sn,
            'camera_slot': slot_key,
        }
        if legacy_id and legacy_id != sn:
            row["legacy_id"] = legacy_id
        profile_id = str(c.get("camera_profile") or "").strip()
        if profile_id:
            row["camera_profile"] = profile_id
        if dsn:
            row['detect_stream_name'] = dsn
        masks = c.get('opencv_masks')
        if masks:
            row['opencv_masks'] = masks
        for key in (
            "tuning_role",
            "detection_interest_zones",
            "detection_interest_zones_required",
        ):
            if key in c:
                row[key] = c[key]
        out.append(row)
    return out


def cameras_for_api(valid_cameras: list) -> list[dict]:
    """Формат для API: id, name, stream_url, stream_url_mjpeg, go2rtc_src (имя потока в Go2RTC)."""
    out: list[dict] = []
    for i, c in enumerate(valid_cameras):
        row = {
            'id': c['id'],
            'name': c['name'],
            'stream_url': f"/go2rtc/stream.html?src={c['stream_name']}",
            'go2rtc_src': c['stream_name'],
            'stream_url_mjpeg': f"/processor/live/{i}",
        }
        slot_key = str(c.get("camera_slot") or "").strip()
        if slot_key:
            row["camera_slot"] = slot_key
        profile_id = str(c.get("camera_profile") or "").strip()
        if profile_id:
            row["camera_profile"] = profile_id
        out.append(row)
    return out


def cameras_for_processor(valid_cameras: list) -> list[dict]:
    """Формат для processor: id, stream_name, optional detect_stream_name."""
    rows: list[dict] = []
    for c in valid_cameras:
        row = {'id': c['id'], 'stream_name': c['stream_name']}
        dsn = (c.get('detect_stream_name') or '').strip()
        if dsn:
            row['detect_stream_name'] = dsn
        slot_key = str(c.get("camera_slot") or "").strip()
        if slot_key:
            row["camera_slot"] = slot_key
        profile_id = str(c.get("camera_profile") or "").strip()
        if profile_id:
            row["camera_profile"] = profile_id
        masks = c.get('opencv_masks')
        if masks:
            row['opencv_masks'] = masks
        rows.append(row)
    return rows
