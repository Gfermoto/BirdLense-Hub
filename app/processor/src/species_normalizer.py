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


def _is_squirrel_or_rodent_name(name: str) -> bool:
    key = _extract_common_for_merge(name or "")
    return any(token in key for token in ("squirrel", "chipmunk", "rodent"))


def _canonical_merge_key(species_name: str) -> str:
    return _extract_common_for_merge(species_name or "") or (species_name or "").lower()


def _collapse_overlapping_generic_bird_detection(
    result_list: list,
    *,
    overlap_min_sec: float,
    min_classifier_confidence: float,
) -> list:
    """Убрать generic ``Bird``, если на том же интервале есть уверенный YOLO-вид.

    Иначе при ``source_priority`` с одинаковым рангом (оба yolo) конфликтный
    блок в merge_detections не срабатывает и в UI остаются и «Bird», и вид.
    """
    if not result_list or len(result_list) < 2:
        return result_list

    def _is_generic_bird_row(det: dict) -> bool:
        name = det.get("species_name") or det.get("species") or ""
        return _canonical_merge_key(name) == "bird"

    def _is_confident_specific_bird(det: dict) -> bool:
        name = det.get("species_name") or det.get("species") or ""
        if not name or _is_generic_bird_row(det):
            return False
        if _is_squirrel_or_rodent_name(name):
            return False
        kind = str(det.get("decision_kind") or "").strip().lower()
        if kind == "accepted_species":
            return True
        clf = det.get("classifier_confidence")
        if clf is not None:
            try:
                return float(clf) >= float(min_classifier_confidence)
            except (TypeError, ValueError):
                return False
        return False

    overlap_min_sec = max(0.0, float(overlap_min_sec or 0.0))
    to_drop: set[int] = set()
    for i, g in enumerate(result_list):
        if not _is_generic_bird_row(g):
            continue
        gs = float(g.get("start_time") or 0)
        ge = float(g.get("end_time") or 0)
        for j, s in enumerate(result_list):
            if i == j or j in to_drop:
                continue
            if not _is_confident_specific_bird(s):
                continue
            ss = float(s.get("start_time") or 0)
            se = float(s.get("end_time") or 0)
            overlap = min(ge, se) - max(gs, ss)
            if overlap >= overlap_min_sec:
                to_drop.add(i)
                prev = s.get("_fusion_used")
                s["_fusion_used"] = f"{prev}+absorbed_generic_bird" if prev else "absorbed_generic_bird"
                break
    if not to_drop:
        return result_list
    out = [d for k, d in enumerate(result_list) if k not in to_drop]
    return out


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
    *,
    absorb_generic_bird=True,
    absorb_generic_bird_overlap_min_sec=0.1,
    absorb_generic_bird_min_classifier_confidence=0.22,
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

    def _is_squirrel_like(name: str) -> bool:
        key = _extract_common_for_merge(name)
        return any(token in key for token in ("squirrel", "chipmunk", "rodent"))

    def _can_frigate_promote(det: dict, ev: dict) -> bool:
        reason = str(det.get("decision_reason") or "").strip().lower()
        if reason not in {"fallback_bird", "fallback_squirrel"}:
            return False
        detector_label = str(det.get("detector_label") or det.get("species_name") or "").strip()
        if not detector_label:
            return False
        if detector_label.lower() == "bird":
            return not _is_squirrel_like(str(ev.get("species") or ev.get("sub_label") or ev.get("label") or ""))
        if detector_label.lower() in {"squirrel", "rodent"}:
            return _is_squirrel_like(str(ev.get("species") or ev.get("sub_label") or ev.get("label") or ""))
        return False

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
            row = dict(d)
            row["species_name"] = species
            row["species"] = species
            row["start_time"] = start
            row["end_time"] = end
            row["confidence"] = conf
            row["source"] = d.get("source", "video")
            row["detection_provider"] = provider
            row["track_id"] = d.get("track_id")
            row["frames"] = d.get("frames")
            row["contributing_providers"] = sorted({provider, *(d.get("contributing_providers") or [])})
            by_key[(key, visit_id)] = row

    # MQTT: мержим в существующую детекцию с наибольшим перекрытием по времени
    for ev in mqtt_events:
        provider = ev.get("source", "mqtt")
        if provider == "birdnet":
            # BirdNET only biases confidence thresholds before YOLO decision-making.
            continue
        if str(provider).strip().lower() == "frigate" and (
            ev.get("_frigate_merge_suppressed") or ev.get("_skip_mqtt_merge_queue")
        ):
            # Excluded labels (cat/dog): keep out of species merge / promotion only.
            continue
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
        if provider == "frigate":
            generic_candidate = None
            best_overlap = -1
            for det in by_key.values():
                if not _can_frigate_promote(det, ev):
                    continue
                es, ee = det.get("start_time", 0), det.get("end_time", 0)
                overlap = min(ee, ev_end) - max(es, ev_start)
                if overlap > best_overlap or (overlap >= 0 and generic_candidate is None):
                    best_overlap = overlap
                    generic_candidate = det
            if generic_candidate is not None:
                generic_candidate["species_name"] = species
                generic_candidate["species"] = species
                generic_candidate["decision_reason"] = "promoted_by_frigate"
                generic_candidate["frigate_promoted_label"] = species
                _merge_into(
                    generic_candidate,
                    conf,
                    ev_start,
                    ev_end,
                    new_provider=provider,
                    new_providers=ev.get("contributing_providers"),
                )
                if cross_source_confidence_bonus and cross_source_confidence_bonus > 0:
                    generic_candidate["confidence"] = min(
                        1.0,
                        float(generic_candidate.get("confidence") or 0) + float(cross_source_confidence_bonus),
                    )
                logger.debug(
                    "merge: Frigate promoted %s for detector fallback %s",
                    species,
                    generic_candidate.get("track_id"),
                )

    result_list = list(by_key.values())

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

    if absorb_generic_bird:
        result_list = _collapse_overlapping_generic_bird_detection(
            result_list,
            overlap_min_sec=float(absorb_generic_bird_overlap_min_sec),
            min_classifier_confidence=float(absorb_generic_bird_min_classifier_confidence),
        )

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
                    if rank_a == rank_b:
                        continue
                    if rank_a < rank_b:
                        to_remove.add(j)
                        logger.debug(
                            "merge: conflict %s vs %s (overlap=%.1fs), keeping %s (higher priority)",
                            a.get("species_name"),
                            b.get("species_name"),
                            overlap,
                            a.get("species_name"),
                        )
                    else:
                        to_remove.add(i)
                        logger.debug(
                            "merge: conflict %s vs %s (overlap=%.1fs), keeping %s (higher priority)",
                            a.get("species_name"),
                            b.get("species_name"),
                            overlap,
                            b.get("species_name"),
                        )
                        break
        result_list = [d for i, d in enumerate(result_list) if i not in to_remove]

    out = sorted(result_list, key=lambda x: x.get("start_time", 0))
    for d in out:
        d.pop("_cross_mqtt_merges", None)
    return out
