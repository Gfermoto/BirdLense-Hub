"""
Species name normalization: Frigate/BirdNET/YOLO → canonical (IOC/eBird style).
"""
import re


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
    YOLO primary; MQTT boosts confidence or adds species if not in YOLO.
    Returns list in API format: species_name, start_time, end_time, confidence, source, track_id, frames.
    """
    from datetime import datetime, timezone

    result = []
    seen_species = set()
    video_duration = (video_end - video_start).total_seconds() if video_end and video_start else 0

    for d in yolo_detections:
        species = d.get("species_name") or d.get("species") or d.get("name", "unknown")
        out = {
            "species_name": species,
            "species": species,
            "start_time": d.get("start_time", 0),
            "end_time": d.get("end_time", video_duration),
            "confidence": d.get("confidence", 0),
            "source": d.get("source", "video"),
            "detection_provider": d.get("detection_provider", "yolo"),
            "track_id": d.get("track_id"),
            "frames": d.get("frames"),
        }
        if "best_frame" in d:
            out["best_frame"] = d["best_frame"]
        result.append(out)
        seen_species.add(species)

    for ev in mqtt_events:
        species = ev.get("species", "unknown")
        conf = ev.get("confidence", 0)
        if species in seen_species:
            for r in result:
                if r.get("species_name") == species:
                    r["confidence"] = max(r.get("confidence", 0), conf)
                    break
            continue
        seen_species.add(species)
        provider = ev.get("source", "mqtt")
        if provider == "birdnet":
            provider = "birdnet_mqtt"
        result.append({
            "species_name": species,
            "species": species,
            "start_time": 0,
            "end_time": video_duration,
            "confidence": conf,
            "source": "video",
            "detection_provider": provider,
        })
    return result
