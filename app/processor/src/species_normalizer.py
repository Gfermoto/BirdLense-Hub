"""
Species name normalization: Frigate/BirdNET/YOLO → canonical (IOC/eBird style).

Поддерживает формат "Scientific (Common)" для слияния детекций.
"""
import logging
import re

logger = logging.getLogger(__name__)


def _extract_common_for_merge(s: str) -> str:
    """
    Извлечь common name для сравнения при слиянии.
    "Cardinalis cardinalis (Northern Cardinal)" -> "Northern Cardinal"
    "Northern Cardinal" -> "Northern Cardinal"
    "Great_Tit" / "Parus major (Great Tit)" -> "great tit"
    """
    if not s or not isinstance(s, str):
        return ""
    s = s.strip().replace("_", " ").replace("-", " ")
    m = re.match(r"^.+?\s*\(([^)]+)\)\s*$", s)
    return m.group(1).strip().lower() if m else s.lower()


def normalize(species: str, mapping: dict = None) -> str:
    """
    Normalize species name to canonical form.
    mapping: config detection.species_mapping, e.g. {"house_sparrow": "House Sparrow"}
    """
    if not species or not isinstance(species, str):
        return "unknown"
    s = species.strip()
    if not s:
        return "unknown"
    mapping = mapping or {}
    key = s.lower().replace(" ", "_").replace("-", "_")
    if key in mapping:
        return mapping[key]
    for k, v in mapping.items():
        if key == k.lower().replace(" ", "_"):
            return v
    return _to_title_case(s)


def _to_title_case(s: str) -> str:
    """Convert 'house_sparrow' or 'house sparrow' to 'House Sparrow'."""
    s = s.replace("_", " ").replace("-", " ")
    parts = s.split()
    return " ".join(p.capitalize() for p in parts if p)


def _event_offset_seconds(ev, video_start):
    """Смещение MQTT-события от начала видео (сек). None если нет timestamp."""
    from datetime import datetime, timezone
    ts_str = ev.get("timestamp")
    if not ts_str:
        return None
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (ts - video_start).total_seconds()
    except (ValueError, TypeError):
        return None


def merge_detections(yolo_detections, mqtt_events, video_start, video_end, merge_window_seconds=5, dedup_window_seconds=45):
    """
    Merge YOLO detections with MQTT (Frigate/BirdNET) events.
    Один результат на вид: max confidence, объединённый интервал времени.
    dedup_window_seconds: детекции одного вида с разрывом > N сек считаются разными визитами.
    MQTT: используем timestamp события (не растягиваем на всё видео).
    """
    from datetime import datetime, timezone

    by_key = {}  # (canonical_key, visit_id) -> detection; visit_id различает визиты с большим разрывом
    video_duration = (video_end - video_start).total_seconds() if video_end and video_start else 0
    mqtt_half_window = merge_window_seconds / 2  # окно вокруг MQTT-события

    def _canonical_key(s):
        return _extract_common_for_merge(s) or (s or "").lower()

    def _merge_into(existing, new_conf, new_start, new_end, new_best_frame=None):
        """Объединить: max confidence, min start, max end."""
        old_conf = existing.get("confidence", 0)
        existing["confidence"] = max(old_conf, new_conf)
        existing["start_time"] = min(existing.get("start_time", 0), new_start)
        existing["end_time"] = max(existing.get("end_time", 0), new_end)
        if new_best_frame is not None and new_conf >= old_conf:
            existing["best_frame"] = new_best_frame

    # YOLO: сортируем по start_time, объединяем по виду с учётом dedup_window
    sorted_yolo = sorted(
        yolo_detections,
        key=lambda d: d.get("start_time", 0),
    )
    for d in sorted_yolo:
        species = d.get("species_name") or d.get("species") or d.get("name", "unknown")
        key = _canonical_key(species)
        conf = d.get("confidence", 0)
        start = d.get("start_time", 0)
        end = d.get("end_time", video_duration)

        # Ищем существующую детекцию того же вида, где (start - existing_end) <= dedup_window
        merged = None
        for k, det in list(by_key.items()):
            if k[0] != key:
                continue
            existing_end = det.get("end_time", 0)
            if start - existing_end <= dedup_window_seconds:
                merged = det
                break

        if merged is not None:
            _merge_into(merged, conf, start, end, d.get("best_frame"))
            logger.debug("merge: YOLO %s into existing", species)
        else:
            visit_id = sum(1 for k in by_key if k[0] == key)
            by_key[(key, visit_id)] = {
                "species_name": species,
                "species": species,
                "start_time": start,
                "end_time": end,
                "confidence": conf,
                "source": d.get("source", "video"),
                "detection_provider": d.get("detection_provider", "yolo"),
                "track_id": d.get("track_id"),
                "frames": d.get("frames"),
            }
            if "best_frame" in d:
                by_key[(key, visit_id)]["best_frame"] = d["best_frame"]

    for ev in mqtt_events:
        species = ev.get("species", "unknown")
        conf = ev.get("confidence", 0)
        key = _canonical_key(species)
        offset = _event_offset_seconds(ev, video_start)
        if offset is not None:
            ev_start = max(0, offset - mqtt_half_window)
            ev_end = min(video_duration, offset + mqtt_half_window)
        else:
            ev_start, ev_end = 0, video_duration

        # Ищем существующую детекцию того же вида (YOLO) и мержим
        merged = next((det for k, det in by_key.items() if k[0] == key), None)
        if merged is not None:
            _merge_into(merged, conf, ev_start, ev_end)
            logger.debug("merge: MQTT %s into YOLO (offset=%.1fs)", species, offset if offset is not None else -1)
            continue
        provider = ev.get("source", "mqtt")
        if provider == "birdnet":
            provider = "birdnet_mqtt"
        by_key[(key, -1)] = {
            "species_name": species,
            "species": species,
            "start_time": ev_start,
            "end_time": ev_end,
            "confidence": conf,
            "source": "video",
            "detection_provider": provider,
        }
        logger.debug("merge: MQTT %s new (offset=%.1fs)", species, offset if offset is not None else -1)

    # Bird = unknown когда один; при наличии любого другого вида — убрать Bird (предпочесть другой)
    # При удалении Bird переносим frames/best_frame в оставшиеся детекции, иначе теряются треки
    bird_key = _canonical_key("Bird")
    result_list = list(by_key.values())
    bird_dets = [d for d in result_list if _canonical_key(d.get("species_name", "")) == bird_key]
    other_dets = [d for d in result_list if _canonical_key(d.get("species_name", "")) != bird_key]
    if bird_dets and other_dets:
        # Переносим frames/best_frame от Bird в детекции без треков (например, только MQTT)
        for other in other_dets:
            if not (other.get("frames") or other.get("best_frame")):
                for bird_d in bird_dets:
                    if bird_d.get("frames") or bird_d.get("best_frame"):
                        other["frames"] = bird_d.get("frames") or other.get("frames")
                        if bird_d.get("best_frame") is not None:
                            other["best_frame"] = bird_d.get("best_frame")
                        if bird_d.get("track_id") is not None:
                            other["track_id"] = bird_d.get("track_id")
                        logger.debug("merge: transferred frames from Bird to %s", other.get("species_name"))
                        break
        result_list = other_dets
        logger.debug("merge: dropped Bird (other species present), kept %d", len(result_list))

    # Сортировка по start_time (раньше появившиеся — первыми)
    return sorted(result_list, key=lambda x: x.get("start_time", 0))
