"""Нормализация имён классов бинарного детектора (совпадает с TwoStageStrategy, CV/ML #367)."""

from __future__ import annotations


def normalize_detector_label(name: str) -> str:
    """
    Привести сырое имя класса YOLO к канонической метке рантайма.

    Совместимо с ``TwoStageStrategy._normalize_detector_label`` (исторически):
    Bird / Rodent / Background / прочее (Title Case).
    """
    raw = str(name or "").replace("_OR_", "/").replace("_", " ").replace("-", " ").strip()
    key = " ".join(raw.lower().split())
    if not key:
        return "Unknown"
    # До проверки «bird» — иначе подстрока «bird» в «background» даёт ложный Bird (#367).
    if key == "background":
        return "Background"
    # DEPRECATED (nabirds-pivot): Rodent detection disabled; legacy BRG/COCO-only.
    if any(token in key for token in ("squirrel", "chipmunk", "rodent", "грызун", "cat")):
        return "Rodent"
    if any(token in key for token in ("bird", "avian")):
        return "Bird"
    return " ".join(part.capitalize() for part in raw.split())
