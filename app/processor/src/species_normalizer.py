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


def merge_detections(
    yolo_detections,
    mqtt_events,
    video_start,
    video_end,
    merge_window_seconds=5,
    dedup_window_seconds=45,
    one_per_species=True,
    source_priority=None,
    cross_source_confidence_bonus=0.0,
    species_mapping=None,
):
    """
    Merge YOLO detections with MQTT (Frigate/BirdNET) events.
    Один результат на вид: max confidence, объединённый интервал времени.
    dedup_window_seconds: детекции одного вида с разрывом > N сек считаются разными визитами.
    one_per_species: если True — гарантированно один результат на вид (объединяем все дубликаты).
    source_priority: при конфликте (разные виды в одном окне) — первый в списке выше приоритет.
    cross_source_confidence_bonus: при первом слиянии MQTT (Frigate/BirdNET) в существующую
        видео-детекцию — разово прибавить к confidence (до 1.0), без дообучения моделей.
    """
    from datetime import datetime, timezone

    source_priority = source_priority or ["yolo", "frigate", "birdnet"]
    species_mapping = species_mapping or {}
    priority_map = {p: i for i, p in enumerate(source_priority)}

    def _provider_rank(provider):
        p = (provider or "").lower()
        if p == "birdnet_mqtt":
            p = "birdnet"
        return priority_map.get(p, 999)

    by_key = {}  # (canonical_key, visit_id) -> detection
    video_duration = (video_end - video_start).total_seconds() if video_end and video_start else 0
    mqtt_half_window = merge_window_seconds / 2

    def _canonical_key(s):
        return _extract_common_for_merge(s) or (s or "").lower()

    def _merge_into(
        existing,
        new_conf,
        new_start,
        new_end,
        new_best_frame=None,
        new_frames=None,
        new_provider=None,
        new_providers=None,
    ):
        old_conf = existing.get("confidence", 0)
        existing["confidence"] = max(old_conf, new_conf)
        existing["start_time"] = min(existing.get("start_time", 0), new_start)
        existing["end_time"] = max(existing.get("end_time", 0), new_end)
        if new_best_frame is not None and new_conf >= old_conf:
            existing["best_frame"] = new_best_frame
        if new_frames and not existing.get("frames"):
            existing["frames"] = new_frames
        if new_provider or new_providers:
            providers = set(existing.get("contributing_providers") or [])
            if new_provider:
                providers.add(new_provider)
            providers.update(p for p in (new_providers or []) if p)
            existing["contributing_providers"] = sorted(providers)

    # YOLO: объединяем по виду. Мержим в детекцию с наименьшим разрывом (не первую попавшуюся)
    sorted_yolo = sorted(yolo_detections, key=lambda d: d.get("start_time", 0))
    for d in sorted_yolo:
        species = d.get("species_name") or d.get("species") or d.get("name", "unknown")
        key = _canonical_key(species)
        conf = d.get("confidence", 0)
        start = d.get("start_time", 0)
        end = d.get("end_time", video_duration)
        provider = d.get("detection_provider", "yolo")

        # Ищем детекцию с наименьшим разрывом (start - existing_end), где разрыв <= dedup_window
        best = None
        best_gap = float("inf")
        for k, det in list(by_key.items()):
            if k[0] != key:
                continue
            existing_end = det.get("end_time", 0)
            gap = start - existing_end
            if gap <= dedup_window_seconds and gap < best_gap:
                best_gap = gap
                best = det

        if best is not None:
            _merge_into(
                best,
                conf,
                start,
                end,
                d.get("best_frame"),
                d.get("frames"),
                new_provider=provider,
                new_providers=d.get("contributing_providers"),
            )
            logger.debug("merge: YOLO %s into existing (gap=%.1fs)", species, best_gap)
        else:
            visit_id = sum(1 for k in by_key if k[0] == key)
            by_key[(key, visit_id)] = {
                "species_name": species,
                "species": species,
                "start_time": start,
                "end_time": end,
                "confidence": conf,
                "source": d.get("source", "video"),
                "detection_provider": provider,
                "track_id": d.get("track_id"),
                "frames": d.get("frames"),
                "contributing_providers": sorted(
                    {provider, *(d.get("contributing_providers") or [])}
                ),
            }
            if "best_frame" in d:
                by_key[(key, visit_id)]["best_frame"] = d["best_frame"]

    # MQTT: мержим в существующую детекцию с наибольшим перекрытием по времени
    for ev in mqtt_events:
        species = normalize(ev.get("species", "unknown"), species_mapping)
        conf = ev.get("confidence", 0)
        key = _canonical_key(species)
        offset = _event_offset_seconds(ev, video_start)
        if offset is not None:
            if offset < -mqtt_half_window or offset > video_duration + mqtt_half_window:
                logger.debug(
                    "merge: skip MQTT %s outside video window (offset=%.1fs)",
                    species,
                    offset,
                )
                continue
            ev_start = max(0, offset - mqtt_half_window)
            ev_end = min(video_duration, offset + mqtt_half_window)
        else:
            ev_start, ev_end = 0, video_duration

        # Ищем детекцию того же вида с наибольшим перекрытием
        merged = None
        best_overlap = -1
        for k, det in by_key.items():
            if k[0] != key:
                continue
            es, ee = det.get("start_time", 0), det.get("end_time", 0)
            overlap = min(ee, ev_end) - max(es, ev_start)
            if overlap > best_overlap or (overlap >= 0 and merged is None):
                best_overlap = overlap
                merged = det
        if merged is None:
            # Нет перекрытия — проверяем близость по времени
            for k, det in by_key.items():
                if k[0] != key:
                    continue
                es, ee = det.get("start_time", 0), det.get("end_time", 0)
                if ev_end >= es - dedup_window_seconds and ev_start <= ee + dedup_window_seconds:
                    merged = det
                    break

        provider = ev.get("source", "mqtt")
        if provider == "birdnet":
            provider = "birdnet_mqtt"
        if merged is not None:
            _merge_into(
                merged,
                conf,
                ev_start,
                ev_end,
                new_provider=provider,
                new_providers=ev.get("contributing_providers"),
            )
            if cross_source_confidence_bonus and cross_source_confidence_bonus > 0:
                n = int(merged.get("_cross_mqtt_merges") or 0) + 1
                merged["_cross_mqtt_merges"] = n
                if n == 1:
                    merged["confidence"] = min(
                        1.0,
                        float(merged.get("confidence") or 0) + float(cross_source_confidence_bonus),
                    )
            logger.debug("merge: MQTT %s into YOLO (offset=%.1fs)", species, offset if offset is not None else -1)
            continue
        # MQTT-only (no overlapping YOLO visit). one_per_species: single bucket (key, -1) and merge.
        if one_per_species:
            existing_mqtt = by_key.get((key, -1))
            if existing_mqtt is not None:
                _merge_into(
                    existing_mqtt,
                    conf,
                    ev_start,
                    ev_end,
                    new_provider=provider,
                    new_providers=ev.get("contributing_providers"),
                )
                logger.debug("merge: MQTT %s into MQTT-only bucket", species)
                continue
            new_vid = -1
        else:
            new_vid = max((vid for (k0, vid) in by_key.keys() if k0 == key), default=-1) + 1

        by_key[(key, new_vid)] = {
            "species_name": species,
            "species": species,
            "start_time": ev_start,
            "end_time": ev_end,
            "confidence": conf,
            "source": "video",
            "detection_provider": provider,
            "contributing_providers": sorted(
                {provider, *(ev.get("contributing_providers") or [])}
            ),
        }
        logger.debug("merge: MQTT %s new (offset=%.1fs)", species, offset if offset is not None else -1)

    # Bird: при наличии другого вида — убрать Bird, перенести frames
    bird_key = _canonical_key("Bird")
    result_list = list(by_key.values())
    bird_dets = [d for d in result_list if _canonical_key(d.get("species_name", "")) == bird_key]
    other_dets = [d for d in result_list if _canonical_key(d.get("species_name", "")) != bird_key]
    if bird_dets and other_dets:
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

    # Финальное объединение: один результат на вид (устраняет дубликаты)
    if one_per_species and len(result_list) > 1:
        by_canonical = {}
        for d in result_list:
            key = _canonical_key(d.get("species_name", ""))
            if key not in by_canonical:
                by_canonical[key] = dict(d)
            else:
                existing = by_canonical[key]
                _merge_into(
                    existing,
                    d.get("confidence", 0),
                    d.get("start_time", 0),
                    d.get("end_time", 0),
                    d.get("best_frame"),
                    d.get("frames"),
                    new_provider=d.get("detection_provider"),
                    new_providers=d.get("contributing_providers"),
                )
                # Сохраняем имя с frames (YOLO) приоритетнее
                if d.get("frames") or d.get("best_frame"):
                    existing["species_name"] = d.get("species_name", existing["species_name"])
                    existing["species"] = existing["species_name"]
        result_list = list(by_canonical.values())
        logger.debug("merge: collapsed to %d species (one per species)", len(result_list))

    # Конфликт: разные виды в одном временном окне — оставляем по source_priority
    conflict_overlap_sec = 3
    if len(result_list) > 1 and source_priority:
        to_remove = set()
        for i, a in enumerate(result_list):
            if i in to_remove:
                continue
            sa, ea = a.get("start_time", 0), a.get("end_time", 0)
            key_a = _canonical_key(a.get("species_name", ""))
            rank_a = _provider_rank(a.get("detection_provider"))
            for j, b in enumerate(result_list):
                if j <= i or j in to_remove:
                    continue
                key_b = _canonical_key(b.get("species_name", ""))
                if key_a == key_b:
                    continue
                sb, eb = b.get("start_time", 0), b.get("end_time", 0)
                overlap = min(ea, eb) - max(sa, sb)
                if overlap >= conflict_overlap_sec:
                    rank_b = _provider_rank(b.get("detection_provider"))
                    if rank_a < rank_b:
                        to_remove.add(j)
                        logger.debug(
                            "merge: conflict %s vs %s (overlap=%.1fs), keeping %s (higher priority)",
                            a.get("species_name"), b.get("species_name"), overlap, a.get("species_name"))
                    else:
                        to_remove.add(i)
                        logger.debug(
                            "merge: conflict %s vs %s (overlap=%.1fs), keeping %s (higher priority)",
                            a.get("species_name"), b.get("species_name"), overlap, b.get("species_name"))
                        break
        result_list = [d for i, d in enumerate(result_list) if i not in to_remove]

    out = sorted(result_list, key=lambda x: x.get("start_time", 0))
    for d in out:
        d.pop("_cross_mqtt_merges", None)
    return out
