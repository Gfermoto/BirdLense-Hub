"""Единый словарь имён: классификатор + арбитраж (Frigate/BirdNET/YOLO) + каталог.

Источник правды для:
- strict ingest (что можно сохранять как вид, не Unknown);
- scope=project в каталоге (все участники пайплайна, birder_eu + служебные виды);
- согласование с ``detection.species_mapping`` в processor.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app_config.app_config import app_config
from services.species_catalog.allowlist import (
    _catalog_allowlist_extra_names,
    _norm_key,
    catalog_classifier_meta,
    load_active_classifier_label_names,
    species_matches_allowlist,
    species_name_match_norm_keys,
)
from services.species_catalog.canon import format_display_casing
from util import load_species_canonical_mapping


def _keys_from_label_lines(lines: tuple[str, ...] | list[str]) -> set[str]:
    keys: set[str] = set()
    for raw in lines:
        for k in species_name_match_norm_keys(str(raw).strip()):
            keys.add(k)
    return keys


def _arbitration_mapping_norm_keys(app_config_get) -> set[str]:
    """Ключи и значения detection/ebird species_mapping + species_canonical_mapping.txt."""
    keys: set[str] = set()
    detection_map = app_config_get("detection.species_mapping") or {}
    ebird_map = app_config_get("ebird.species_mapping") or {}
    if not isinstance(detection_map, dict):
        detection_map = {}
    if not isinstance(ebird_map, dict):
        ebird_map = {}
    merged = {**detection_map, **ebird_map}
    for variant, canonical in merged.items():
        keys |= species_name_match_norm_keys(str(variant).strip())
        keys |= species_name_match_norm_keys(str(canonical).strip())
    canonical_file = load_species_canonical_mapping() or {}
    for variant, canonical in canonical_file.items():
        keys |= species_name_match_norm_keys(str(variant).strip())
        keys |= species_name_match_norm_keys(str(canonical).strip())
    regional = app_config_get("processor.regional_species") or []
    if isinstance(regional, (list, tuple)):
        for name in regional:
            keys |= species_name_match_norm_keys(str(name).strip())
    return keys


def _classifier_canonical_alias_keys(app_config_get) -> set[str]:
    """Метки классификатора + каноническое написание (EURASIAN MAGPIE → Eurasian Magpie)."""
    keys: set[str] = set()
    for raw in load_active_classifier_label_names(app_config_get) or ():
        line = str(raw).strip()
        if not line:
            continue
        keys |= species_name_match_norm_keys(line)
        keys.add(_norm_key(format_display_casing(line)))
    return keys


@dataclass(frozen=True)
class SpeciesVocabularySnapshot:
    classifier_engine: str
    classifier_class_count: int
    classifier_norm_keys: frozenset[str]
    arbitration_norm_keys: frozenset[str]
    project_norm_keys: frozenset[str]

    def allows_ingest_name(self, *names: str, mapping: dict | None = None) -> bool:
        mapping = mapping or load_species_canonical_mapping()
        combined = self.classifier_norm_keys | self.arbitration_norm_keys
        for name in names:
            if not str(name or "").strip():
                continue
            if species_matches_allowlist(str(name).strip(), combined, mapping):
                return True
        return False


@lru_cache(maxsize=2)
def _vocabulary_snapshot_cached(strict_ingest_flag: bool) -> SpeciesVocabularySnapshot:
    getter = app_config.get
    classifier_keys = _keys_from_label_lines(load_active_classifier_label_names(getter) or ())
    classifier_keys |= _classifier_canonical_alias_keys(getter)
    for extra in _catalog_allowlist_extra_names(getter):
        classifier_keys |= species_name_match_norm_keys(extra)
    arbitration_keys = _arbitration_mapping_norm_keys(getter)
    project_keys = set(classifier_keys) | set(arbitration_keys)
    meta = catalog_classifier_meta(getter)
    return SpeciesVocabularySnapshot(
        classifier_engine=str(meta.get("classifier_engine") or ""),
        classifier_class_count=int(meta.get("classifier_class_count") or 0),
        classifier_norm_keys=frozenset(classifier_keys),
        arbitration_norm_keys=frozenset(arbitration_keys),
        project_norm_keys=frozenset(project_keys),
    )


def get_species_vocabulary_snapshot() -> SpeciesVocabularySnapshot:
    """Снимок словаря (кэш на процесс; сброс при смене конфига — restart)."""
    strict = bool(app_config.get("species.catalog_strict_ingest"))
    return _vocabulary_snapshot_cached(strict)


def clear_species_vocabulary_cache() -> None:
    _vocabulary_snapshot_cached.cache_clear()


__all__ = [
    "SpeciesVocabularySnapshot",
    "clear_species_vocabulary_cache",
    "get_species_vocabulary_snapshot",
]
