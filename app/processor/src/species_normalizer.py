"""
Species name normalization: Frigate/BirdNET/YOLO → canonical (IOC/eBird style).

Поддерживает формат "Scientific (Common)" для слияния детекций.
"""

import logging
import re

logger = logging.getLogger(__name__)


def _normalize_lookup_key(value: str) -> str:
    s = str(value or "").strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _split_scientific_common(value: str) -> tuple[str | None, str | None]:
    s = str(value or "").strip()
    if not s:
        return None, None
    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", s)
    if not m:
        return None, s
    left = (m.group(1) or "").strip() or None
    right = (m.group(2) or "").strip() or None
    return left, right


def _normalize_candidates(value: str) -> list[str]:
    scientific, common = _split_scientific_common(value)
    out: list[str] = []
    for candidate in (value, common, scientific):
        key = _normalize_lookup_key(candidate or "")
        if key and key not in out:
            out.append(key)
    return out


def _mapping_lookup(species: str, mapping: dict) -> str | None:
    if not mapping:
        return None
    value = str(species or "").strip()
    if not value:
        return None
    index: dict[str, str] = {}
    for mk, mv in mapping.items():
        mapped = str(mv or "").strip()
        if not mapped:
            continue
        for candidate in _normalize_candidates(str(mk or "")):
            index.setdefault(candidate, mapped)
    for candidate in _normalize_candidates(value):
        resolved = index.get(candidate)
        if resolved:
            return resolved
    return None


def _append_unique_str_list(row: dict, key: str, values) -> None:
    bucket = [str(x).strip() for x in (row.get(key) or []) if str(x).strip()]
    for v in values or []:
        s = str(v or "").strip()
        if s and s not in bucket:
            bucket.append(s)
    if bucket:
        row[key] = bucket


def _event_aliases(ev: dict) -> tuple[list[str], list[str]]:
    aliases: list[str] = []
    scientific: list[str] = []
    for k in ("species", "sub_label", "label"):
        v = str((ev or {}).get(k) or "").strip()
        if v and v.lower() not in {"bird", "unknown"} and v not in aliases:
            aliases.append(v)
    sci = str((ev or {}).get("scientific_name") or "").strip()
    if sci:
        scientific.append(sci)
    return aliases, scientific


def _is_frigate_standalone_row(row: dict) -> bool:
    provider = str(row.get("detection_provider") or "").strip().lower()
    kind = str(row.get("decision_kind") or "").strip().lower()
    return provider == "frigate" and kind in {"frigate_standalone", "frigate_standalone_excluded"}


def _merge_absorb_trace_reason(generic_row: dict, species_row: dict) -> str:
    """Совпадает по смыслу с hypothesis_arbitration (без циклического импорта)."""
    if _is_frigate_standalone_row(generic_row) and _is_frigate_standalone_row(species_row):
        return "absorbed_generic_into_frigate_species"
    return "absorbed_generic_into_species"


def _apply_arbitration_trace_for_merge(row: dict, reason: str) -> None:
    """Как hypothesis_arbitration._tag_row — для provenance после merge conflict."""
    previous_reason = row.get("decision_reason")
    if previous_reason and previous_reason != reason and "decision_reason_before_arbitration" not in row:
        row["decision_reason_before_arbitration"] = previous_reason
    row["decision_reason"] = reason
    row["arbitration_reason"] = reason
    tag = str(row.get("_fusion_used") or "").strip()
    row["_fusion_used"] = f"{tag}+{reason}" if tag else reason


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
    hit = _mapping_lookup(s, mapping)
    if hit:
        return hit
    return _to_title_case(s)


def _to_title_case(s: str) -> str:
    """Convert 'house_sparrow' or 'house sparrow' to 'House Sparrow'.

    Дефисы внутри слова не разрываем (IOC/eBird: Red-breasted Flycatcher, Eagle-Owl).
    """
    s = s.replace("_", " ").strip()
    out: list[str] = []
    for w in s.split():
        if not w:
            continue
        if "-" in w:
            out.append("-".join(seg.capitalize() for seg in w.split("-") if seg))
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _is_rodent_taxon_name(name: str) -> bool:
    key = _extract_common_for_merge(name or "")
    return any(token in key for token in ("squirrel", "chipmunk", "rodent", "sciurus", "грызун"))


def _canonical_merge_key(species_name: str) -> str:
    return _extract_common_for_merge(species_name or "") or (species_name or "").lower()


def _is_generic_bird_key(key: str) -> bool:
    return str(key or "").strip().lower() == "bird"


def _conflict_score(det: dict) -> tuple:
    decision_kind = str(det.get("decision_kind") or "").strip().lower()
    accepted_species = 1 if decision_kind == "accepted_species" else 0
    classifier_conf = float(det.get("classifier_confidence") or 0.0)
    confidence = float(det.get("confidence") or 0.0)
    duration = max(0.0, float(det.get("end_time") or 0.0) - float(det.get("start_time") or 0.0))
    provider_count = len(set(det.get("contributing_providers") or []))
    name = str(det.get("species_name") or det.get("species") or "").strip().lower()
    provider = str(det.get("detection_provider") or det.get("source") or "").strip().lower()
    track_id = det.get("track_id")
    try:
        track_rank = int(track_id) if track_id is not None else 0
    except (TypeError, ValueError):
        track_rank = 0
    # Deterministic tie-breaker: stronger evidence first, lexical fallback for stability.
    return (accepted_species, classifier_conf, confidence, duration, provider_count, name, provider, -track_rank)


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
        if _is_rodent_taxon_name(name):
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


def _is_pure_yolo_generic_bird_fragment(det: dict) -> bool:
    name = det.get("species_name") or det.get("species") or ""
    if _canonical_merge_key(name) != "bird":
        return False
    provider = str(det.get("detection_provider") or "").strip().lower()
    if provider != "yolo":
        return False
    providers = {str(p).strip().lower() for p in (det.get("contributing_providers") or []) if str(p).strip()}
    if providers and providers != {"yolo"}:
        return False
    reason = str(det.get("decision_reason") or "").strip().lower()
    return reason in {"fallback_bird", "fallback_detector_generic"}


def _should_keep_generic_bird_fragments_separate(group: list[dict]) -> bool:
    return len(group) > 1 and all(_is_pure_yolo_generic_bird_fragment(det) for det in group)


def _should_keep_distinct_track_fragments_separate(group: list[dict]) -> bool:
    """Same species, different ByteTrack ids — keep separate visits in one clip."""
    if len(group) <= 1:
        return False
    track_ids: list[int] = []
    for det in group:
        tid = det.get("track_id")
        if tid is None:
            return False
        try:
            track_ids.append(int(tid))
        except (TypeError, ValueError):
            return False
    return len(set(track_ids)) == len(track_ids) > 1


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
    one_per_species_keep_distinct_tracks=False,
    source_priority=None,
    cross_source_confidence_bonus=0.0,
    species_mapping=None,
    *,
    absorb_generic_bird=True,
    absorb_generic_bird_overlap_min_sec=0.1,
    absorb_generic_bird_min_classifier_confidence=0.22,
    preserve_equal_rank_conflicts_for_arbitration=False,
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
        new_aliases=None,
        new_scientific_names=None,
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
        _append_unique_str_list(existing, "source_aliases", new_aliases)
        _append_unique_str_list(existing, "source_scientific_names", new_scientific_names)

    def _is_rodent_like_ev_label(name: str) -> bool:
        key = _extract_common_for_merge(name)
        return any(token in key for token in ("squirrel", "chipmunk", "rodent", "sciurus", "грызун"))

    def _can_frigate_promote(det: dict, ev: dict) -> bool:
        reason = str(det.get("decision_reason") or "").strip().lower()
        # Weak classifier → review_only_generic_bird: still promote from Frigate sub_label.
        if reason not in {
            "fallback_bird",
            "fallback_rodent",
            "fallback_squirrel",
            "review_only_generic_bird",
        }:
            return False
        detector_label = str(det.get("detector_label") or det.get("species_name") or "").strip()
        if not detector_label:
            return False
        if detector_label.lower() == "bird":
            return not _is_rodent_like_ev_label(str(ev.get("species") or ev.get("sub_label") or ev.get("label") or ""))
        if detector_label.lower() in {"squirrel", "rodent"}:
            return _is_rodent_like_ev_label(str(ev.get("species") or ev.get("sub_label") or ev.get("label") or ""))
        return False

    def _track_sort_value(value) -> int:
        try:
            return int(value) if value is not None else 0
        except (TypeError, ValueError):
            return 0

    def _mqtt_sort_key(ev: dict) -> tuple:
        provider = str((ev or {}).get("source") or "").strip().lower()
        species = str((ev or {}).get("species") or (ev or {}).get("sub_label") or (ev or {}).get("label") or "").strip()
        camera = str((ev or {}).get("camera") or "").strip().lower()
        timestamp = str((ev or {}).get("timestamp") or "").strip()
        try:
            confidence = float((ev or {}).get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        return (provider, timestamp, camera, species.lower(), -confidence)

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

        if best is not None and one_per_species_keep_distinct_tracks:
            best_tid = best.get("track_id")
            cur_tid = d.get("track_id")
            try:
                if best_tid is not None and cur_tid is not None and int(best_tid) != int(cur_tid):
                    best = None
            except (TypeError, ValueError):
                pass
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
                new_aliases=d.get("source_aliases"),
                new_scientific_names=d.get("source_scientific_names"),
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
            _append_unique_str_list(row, "source_aliases", d.get("source_aliases"))
            _append_unique_str_list(
                row,
                "source_scientific_names",
                d.get("source_scientific_names"),
            )
            by_key[(key, visit_id)] = row

    # MQTT: мержим в существующую детекцию с наибольшим перекрытием по времени
    for ev in sorted((mqtt_events or []), key=_mqtt_sort_key):
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
        ev_aliases, ev_scientific = _event_aliases(ev)
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
                new_aliases=ev_aliases,
                new_scientific_names=ev_scientific,
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
                _append_unique_str_list(generic_candidate, "source_aliases", ev_aliases)
                _append_unique_str_list(
                    generic_candidate,
                    "source_scientific_names",
                    ev_scientific,
                )
                _merge_into(
                    generic_candidate,
                    conf,
                    ev_start,
                    ev_end,
                    new_provider=provider,
                    new_providers=ev.get("contributing_providers"),
                    new_aliases=ev_aliases,
                    new_scientific_names=ev_scientific,
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
        grouped: dict[str, list[dict]] = {}
        for d in result_list:
            grouped.setdefault(_canonical_key(d.get("species_name", "")), []).append(dict(d))

        collapsed: list[dict] = []
        for key, group in grouped.items():
            if _should_keep_generic_bird_fragments_separate(group):
                collapsed.extend(sorted(group, key=lambda item: item.get("start_time", 0)))
                logger.debug("merge: preserved %d fragmented generic bird visits", len(group))
                continue
            if one_per_species_keep_distinct_tracks and _should_keep_distinct_track_fragments_separate(group):
                collapsed.extend(sorted(group, key=lambda item: item.get("start_time", 0)))
                logger.debug("merge: preserved %d distinct-track visits for species %s", len(group), key)
                continue
            group_sorted = sorted(
                group,
                key=lambda item: (
                    -float(item.get("confidence") or 0.0),
                    float(item.get("start_time") or 0.0),
                    float(item.get("end_time") or 0.0),
                    str(item.get("detection_provider") or "").strip().lower(),
                    _track_sort_value(item.get("track_id")),
                ),
            )
            existing = group_sorted[0]
            for d in group_sorted[1:]:
                _merge_into(
                    existing,
                    d.get("confidence", 0),
                    d.get("start_time", 0),
                    d.get("end_time", 0),
                    d.get("best_frame"),
                    d.get("frames"),
                    new_provider=d.get("detection_provider"),
                    new_providers=d.get("contributing_providers"),
                    new_aliases=d.get("source_aliases"),
                    new_scientific_names=d.get("source_scientific_names"),
                )
                # Сохраняем имя с frames (YOLO) приоритетнее
                if d.get("frames") or d.get("best_frame"):
                    existing["species_name"] = d.get("species_name", existing["species_name"])
                    existing["species"] = existing["species_name"]
            collapsed.append(existing)
        result_list = collapsed
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
                    # Product rule: when generic Bird overlaps specific species,
                    # prefer species even if source priority differs.
                    if _is_generic_bird_key(key_a) and not _is_generic_bird_key(key_b):
                        _apply_arbitration_trace_for_merge(b, _merge_absorb_trace_reason(a, b))
                        to_remove.add(i)
                        break
                    if _is_generic_bird_key(key_b) and not _is_generic_bird_key(key_a):
                        _apply_arbitration_trace_for_merge(a, _merge_absorb_trace_reason(b, a))
                        to_remove.add(j)
                        continue
                    rank_b = _provider_rank(b.get("detection_provider"))
                    if rank_a == rank_b:
                        if (
                            preserve_equal_rank_conflicts_for_arbitration
                            and not _is_generic_bird_key(key_a)
                            and not _is_generic_bird_key(key_b)
                        ):
                            # Keep equal-rank specific conflicts for downstream
                            # arbitration after evidence enrichment.
                            continue
                        score_a = _conflict_score(a)
                        score_b = _conflict_score(b)
                        if score_a == score_b:
                            # Stable lexical fallback when scores are identical.
                            if str(a.get("species_name") or "") <= str(b.get("species_name") or ""):
                                to_remove.add(j)
                            else:
                                to_remove.add(i)
                                break
                        elif score_a > score_b:
                            to_remove.add(j)
                        else:
                            to_remove.add(i)
                            break
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

    out = sorted(
        result_list,
        key=lambda x: (
            float(x.get("start_time") or 0.0),
            float(x.get("end_time") or 0.0),
            str(x.get("species_name") or x.get("species") or "").strip().lower(),
            str(x.get("detection_provider") or "").strip().lower(),
            _track_sort_value(x.get("track_id")),
        ),
    )
    for d in out:
        d.pop("_cross_mqtt_merges", None)
    return out
