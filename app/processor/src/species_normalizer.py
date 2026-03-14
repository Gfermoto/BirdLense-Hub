"""
Species name normalization: Frigate/BirdNET/YOLO → canonical (IOC/eBird style).

Поддерживает формат "Scientific (Common)" для слияния детекций.
"""
import re


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


def merge_detections(yolo_detections, mqtt_events, video_start, video_end, merge_window_seconds=5, dedup_window_seconds=45):
    """
    Merge YOLO detections with MQTT (Frigate/BirdNET) events.
    Один результат на вид: max confidence, объединённый интервал времени.
    dedup_window_seconds: детекции одного вида с разрывом > N сек считаются разными визитами.
    """
    from datetime import datetime, timezone

    by_key = {}  # (canonical_key, visit_id) -> detection; visit_id различает визиты с большим разрывом
    video_duration = (video_end - video_start).total_seconds() if video_end and video_start else 0

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
        # Ищем любую существующую детекцию того же вида (YOLO) и мержим
        merged = next((det for k, det in by_key.items() if k[0] == key), None)
        if merged is not None:
            _merge_into(merged, conf, 0, video_duration)
            continue
        provider = ev.get("source", "mqtt")
        if provider == "birdnet":
            provider = "birdnet_mqtt"
        by_key[(key, -1)] = {
            "species_name": species,
            "species": species,
            "start_time": 0,
            "end_time": video_duration,
            "confidence": conf,
            "source": "video",
            "detection_provider": provider,
        }

    # Сортировка по start_time (раньше появившиеся — первыми)
    return sorted(by_key.values(), key=lambda x: x.get("start_time", 0))
