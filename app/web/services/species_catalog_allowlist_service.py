"""Allowlist имён видов по обучающему датасету классификатора (YOLO cls).

Файл со списком классов (по одному на строку) в формате отображения в Hub,
как после нормализации процессора: ``Scientific (Common)`` с пробелами.

Типичный источник: ``scripts/datasets/dump_classifier_allowlist.py`` →
``processor/models/classification/weights/class_names.txt`` рядом с ``best.pt``.

Ключ конфигурации: ``species.catalog_allowlist_file`` (путь относительно корня
``app/processor`` или абсолютный). Пусто — allowlist выключен.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

from util import load_species_canonical_mapping, normalize_species_to_canonical


def _processor_root() -> str:
    web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(web_dir, '..', 'processor'))


def _norm_key(name: str) -> str:
    if not name:
        return ''
    s = name.strip().lower()
    s = s.replace('_', ' ').replace('-', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s


def resolve_allowlist_path(app_config_get) -> str | None:
    rel = (app_config_get('species.catalog_allowlist_file') or '').strip()
    if not rel:
        return None
    if os.path.isabs(rel):
        return rel
    return os.path.join(_processor_root(), rel)


@lru_cache(maxsize=4)
def _load_allowlist_norm_keys_cached(abspath: str) -> frozenset[str]:
    keys: set[str] = set()
    with open(abspath, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.split('#', 1)[0].strip()
            if not line:
                continue
            keys.add(_norm_key(line))
    return frozenset(keys)


def load_catalog_allowlist_norm_keys(app_config_get) -> frozenset[str] | None:
    """Множество нормализованных ключей или None, если allowlist не задан / файла нет."""
    path = resolve_allowlist_path(app_config_get)
    if not path or not os.path.isfile(path):
        return None
    return _load_allowlist_norm_keys_cached(os.path.abspath(path))


def clear_allowlist_cache() -> None:
    _load_allowlist_norm_keys_cached.cache_clear()


def species_name_match_norm_keys(name: str, mapping: dict[str, str] | None = None) -> set[str]:
    """Ключи для сопоставления строки каталога с allowlist (как у alignment)."""
    keys: set[str] = set()
    if not name or not str(name).strip():
        return keys
    mapping = mapping or load_species_canonical_mapping()
    stripped = str(name).strip()
    keys.add(_norm_key(stripped))
    canon = normalize_species_to_canonical(stripped, mapping)
    keys.add(_norm_key(canon))
    m = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', stripped)
    if m:
        keys.add(_norm_key(m.group(1).strip()))
        keys.add(_norm_key(m.group(2).strip()))
    return {k for k in keys if k}


def species_matches_allowlist(
    display_name: str,
    allow_keys: frozenset[str],
    mapping: dict[str, str] | None = None,
) -> bool:
    if not allow_keys:
        return True
    return bool(species_name_match_norm_keys(display_name, mapping) & allow_keys)


def ingest_name_matches_allowlist(
    raw_or_canonical: str,
    allow_keys: frozenset[str] | None,
    mapping: dict[str, str] | None = None,
) -> bool:
    """Для входящей строки до/после резолвера: есть ли пересечение с allowlist."""
    if not allow_keys:
        return True
    return species_matches_allowlist(raw_or_canonical, allow_keys, mapping)
