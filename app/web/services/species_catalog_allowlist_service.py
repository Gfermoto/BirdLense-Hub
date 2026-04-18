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


def _split_scientific_common_display(s: str) -> tuple[str, str] | None:
    """Разбор ``Scientific (Common)`` без regex с вложенными квантификаторами (ReDoS)."""
    stripped = str(s).strip()
    if not stripped.endswith(")"):
        return None
    open_idx = stripped.rfind("(")
    if open_idx <= 0:
        return None
    sci = stripped[:open_idx].rstrip()
    common = stripped[open_idx + 1 : -1].strip()
    if not sci or not common:
        return None
    return (sci, common)


def _processor_root() -> str:
    web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(web_dir, "..", "processor"))


def _norm_key(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def resolve_allowlist_path(app_config_get) -> str | None:
    """Абсолютный путь к файлу allowlist классификатора или None, если не задан."""
    rel = (app_config_get("species.catalog_allowlist_file") or "").strip()
    if not rel:
        return None
    if os.path.isabs(rel):
        return rel
    return os.path.join(_processor_root(), rel)


@lru_cache(maxsize=4)
def _load_allowlist_norm_keys_cached(abspath: str) -> frozenset[str]:
    """Load norm keys from allowlist.

    For entries in "Scientific (Common)" format, also adds the common name as a
    separate key so DB species stored with just common names (e.g. "Eurasian Blue Tit")
    match against allowlist entries like "Cyanistes caeruleus (Eurasian Blue Tit)".
    """
    keys: set[str] = set()
    with open(abspath, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            keys.add(_norm_key(line))
            pair = _split_scientific_common_display(line)
            if pair:
                keys.add(_norm_key(pair[0]))
                keys.add(_norm_key(pair[1]))
    return frozenset(keys)


def load_catalog_allowlist_norm_keys(app_config_get) -> frozenset[str] | None:
    """Множество нормализованных ключей или None, если allowlist не задан / файла нет."""
    path = resolve_allowlist_path(app_config_get)
    if not path or not os.path.isfile(path):
        return None
    return _load_allowlist_norm_keys_cached(os.path.abspath(path))


def clear_allowlist_cache() -> None:
    """Очистить lru_cache загрузки allowlist (после смены файла или конфига)."""
    _load_allowlist_norm_keys_cached.cache_clear()
    _load_allowlist_names_cached.cache_clear()


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
    pair = _split_scientific_common_display(stripped)
    if pair:
        keys.add(_norm_key(pair[0]))
        keys.add(_norm_key(pair[1]))
    return {k for k in keys if k}


def species_matches_allowlist(
    display_name: str,
    allow_keys: frozenset[str],
    mapping: dict[str, str] | None = None,
) -> bool:
    """True если отображаемое имя пересекается с ключами allowlist (пустой allowlist = всё разрешено)."""
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


@lru_cache(maxsize=4)
def _load_allowlist_names_cached(abspath: str) -> tuple[str, ...]:
    """Raw display names from allowlist file (preserved case, stripped)."""
    names: list[str] = []
    with open(abspath, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if line:
                names.append(line)
    return tuple(names)


def load_catalog_allowlist_names(app_config_get) -> tuple[str, ...] | None:
    """Список имён классов из allowlist-файла или None, если не задан."""
    path = resolve_allowlist_path(app_config_get)
    if not path or not os.path.isfile(path):
        return None
    return _load_allowlist_names_cached(os.path.abspath(path))


def allowlist_scientific_name_for_display_name(
    display_name: str,
    app_config_get,
) -> str | None:
    """Биноминальное имя из строки allowlist «Scientific (Common)» при совпадении с видом в БД.

    Классификатор хранит «Pica pica (Eurasian Magpie)», а Species.name часто только
    «Eurasian Magpie» — для Wikipedia/iNaturalist надёжнее искать по **Pica pica**,
    иначе попадаем на нерелевантную страницу общего имени.
    """
    if not (display_name or "").strip():
        return None
    target_keys = species_name_match_norm_keys(display_name)
    if not target_keys:
        return None
    path = resolve_allowlist_path(app_config_get)
    if not path or not os.path.isfile(path):
        return None
    abspath = os.path.abspath(path)
    for raw in _load_allowlist_names_cached(abspath):
        pair = _split_scientific_common_display(raw)
        if not pair:
            continue
        sci, common = pair
        line_keys = {
            _norm_key(raw),
            _norm_key(sci),
            _norm_key(common),
        }
        if target_keys & line_keys:
            return sci.strip()
    return None
