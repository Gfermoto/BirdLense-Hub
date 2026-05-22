"""Нормализация имён классов бинарного детектора (совпадает с TwoStageStrategy, CV/ML #367)."""

from __future__ import annotations

from typing import AbstractSet, Any, Iterable, Mapping


def _title_case_label(raw: str) -> str:
    return " ".join(part.capitalize() for part in raw.split())


def detector_native_class_labels_enabled(config: Mapping[str, Any] | None) -> bool:
    """Trapper / multi-species: сохранять имена классов модели (без схлопывания в Bird/Rodent)."""
    if not config:
        return False
    return bool(config.get("processor.detector_native_class_labels", False))


def normalize_detector_label(name: str, *, native: bool = False) -> str:
    """
    Привести сырое имя класса YOLO к канонической метке рантайма.

    ``native=True`` (``processor.detector_native_class_labels``): Title Case из ``model.names``.
    Иначе legacy: Bird / Rodent / Background.
    """
    raw = str(name or "").replace("_OR_", "/").replace("_", " ").replace("-", " ").strip()
    key = " ".join(raw.lower().split())
    if not key:
        return "Unknown"
    if key == "background":
        return "Background"
    if native:
        return _title_case_label(raw)
    # DEPRECATED (nabirds-pivot): Rodent detection disabled; legacy BRG/COCO-only.
    if any(token in key for token in ("squirrel", "chipmunk", "rodent", "грызун", "cat")):
        return "Rodent"
    if any(token in key for token in ("bird", "avian")):
        return "Bird"
    return _title_case_label(raw)


def resolve_detector_scope_set(
    raw_scope: Iterable[str] | None,
    config: Mapping[str, Any] | None = None,
) -> AbstractSet[str] | None:
    """
    ``None`` — не фильтровать по scope (все классы модели после allowlist).

    Пустой список ``[]`` — то же. Непустой список — whitelist нормализованных меток.
    """
    if raw_scope is None:
        return None
    if isinstance(raw_scope, (list, tuple, set)) and len(raw_scope) == 0:
        return None
    native = detector_native_class_labels_enabled(config)
    out: set[str] = set()
    for item in raw_scope:
        s = str(item or "").strip()
        if not s:
            continue
        out.add(normalize_detector_label(s, native=native))
    return out if out else None
