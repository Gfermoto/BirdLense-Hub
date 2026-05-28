"""Allowlist имён видов по обучающему датасету классификатора (YOLO cls).

Файл со списком классов (по одному на строку) в формате отображения в Hub,
как после нормализации процессора: ``Scientific (Common)`` с пробелами.

Типичный источник: ``scripts/datasets/dump_classifier_allowlist.py`` →
``{variant}/class_labels.txt`` активного Birder EU классификатора (#516).

Ключ конфигурации: ``species.catalog_allowlist_file`` (путь относительно корня
``app/processor`` или абсолютный). Пусто — allowlist выключен.

Реализация живёт в ``services/species_catalog/``; корневой shim —
``services/species_catalog_allowlist_service.py`` (#344).
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

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


def _web_app_dir() -> str:
    """Каталог ``app/web`` (где лежит ``app.py``), независимо от глубины вложенности модуля."""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, "app.py")):
            return d
        d = os.path.dirname(d)
    raise RuntimeError("BirdLense web app root (app.py) not found from species_catalog")


def _processor_root() -> str:
    web_dir = _web_app_dir()
    return os.path.abspath(os.path.join(web_dir, "..", "processor"))


def _classifier_engine_name(app_config_get) -> str:
    return str(app_config_get("processor.classifier_engine", "birder_eu") or "birder_eu").strip().lower()


def _birder_labels_dir(app_config_get) -> str:
    variant = str(app_config_get("processor.birder_eu_variant") or "convnext_v2_tiny_eu-common256px").strip()
    rel = (
        app_config_get("processor.models.classifier_openvino")
        or app_config_get("processor.models.classifier_birder_eu_openvino")
        or f"models/classification/weights/{variant}_openvino_model"
    )
    return rel if os.path.isabs(rel) else os.path.join(_processor_root(), rel)


def _efficientnet_weights_dir(app_config_get) -> str:
    rel = (
        app_config_get(
            "processor.models.classifier_efficientnet_b2",
            "models/classification/weights/efficientnet_b2_global",
        )
        or "models/classification/weights/efficientnet_b2_global"
    )
    return rel if os.path.isabs(rel) else os.path.join(_processor_root(), rel)


def _classifier_engine_allowlist_path(app_config_get) -> str | None:
    engine = _classifier_engine_name(app_config_get)
    if engine == "birder_eu":
        base = _birder_labels_dir(app_config_get)
        return os.path.join(base, "class_labels.txt")
    if engine != "efficientnet_b2":
        return None
    base = _efficientnet_weights_dir(app_config_get)
    if os.path.isdir(base):
        candidate = os.path.join(base, "class_labels.txt")
        return candidate
    if base.endswith(".txt"):
        return base
    return os.path.join(base, "class_labels.txt")


def _catalog_use_active_classifier_labels(app_config_get) -> bool:
    """Каталог allowlist = метки активного классификатора (не union с legacy YOLO)."""
    raw = app_config_get("species.catalog_allowlist_use_active_classifier")
    if raw is None:
        return True
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _normalize_classifier_label(name: str) -> str:
    return str(name or "").replace("_OR_", "/").replace("_", " ").strip()


@lru_cache(maxsize=4)
def _load_efficientnet_id2label_cached(weights_dir: str) -> tuple[str, ...]:
    cfg_path = Path(weights_dir) / "config.json"
    if not cfg_path.is_file():
        return ()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    raw = cfg.get("id2label") or {}
    out: list[str] = []
    for _k in sorted(raw.keys(), key=lambda x: int(x)):
        label = _normalize_classifier_label(raw[_k])
        if label:
            out.append(label)
    return tuple(out)


def load_active_classifier_label_names(app_config_get) -> tuple[str, ...] | None:
    """Имена классов, которые активный классификатор может выдать на кропе."""
    engine = _classifier_engine_name(app_config_get)
    if engine == "birder_eu":
        path = os.path.join(_birder_labels_dir(app_config_get), "class_labels.txt")
        if os.path.isfile(path):
            return _load_allowlist_names_cached(os.path.abspath(path))
        return None
    if engine == "efficientnet_b2":
        labels = _load_efficientnet_id2label_cached(_efficientnet_weights_dir(app_config_get))
        return labels if labels else None
    path = _resolve_configured_allowlist_path(app_config_get) or _classifier_engine_allowlist_path(app_config_get)
    if path and os.path.isfile(path):
        return _load_allowlist_names_cached(os.path.abspath(path))
    return None


def catalog_classifier_meta(app_config_get) -> dict[str, str | int]:
    engine = _classifier_engine_name(app_config_get)
    labels = load_active_classifier_label_names(app_config_get) or ()
    return {
        "classifier_engine": engine,
        "classifier_class_count": len(labels),
    }


def _norm_key(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _catalog_allowlist_extra_names(app_config_get) -> tuple[str, ...]:
    """Классы вне EfficientNet (напр. Rodent из детектора Trapper), не в class_labels.txt."""
    raw = app_config_get("species.catalog_allowlist_extra") or ["Rodent"]
    if isinstance(raw, str):
        raw = [raw]
    names: list[str] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            line = str(item or "").split("#", 1)[0].strip()
            if line:
                names.append(line)
    return tuple(names)


def _resolve_configured_allowlist_path(app_config_get) -> str | None:
    rel = (app_config_get("species.catalog_allowlist_file") or "").strip()
    if not rel:
        return None
    if os.path.isabs(rel):
        return rel
    return os.path.join(_processor_root(), rel)


def _resolve_supplement_allowlist_paths(app_config_get) -> list[str]:
    """Явный supplement (не legacy YOLO class_names из catalog_allowlist_file)."""
    out: list[str] = []
    rel = (app_config_get("species.catalog_allowlist_supplement_file") or "").strip()
    if not rel:
        return out
    path = rel if os.path.isabs(rel) else os.path.join(_processor_root(), rel)
    if os.path.isfile(path):
        out.append(os.path.abspath(path))
    return out


def resolve_all_allowlist_paths(app_config_get) -> list[str]:
    """Файлы allowlist (если не используем id2label активного классификатора)."""
    follow_engine = str(
        app_config_get("species.catalog_allowlist_follow_classifier_engine", True)
    ).strip().lower() in ("1", "true", "yes", "on")
    if follow_engine and _catalog_use_active_classifier_labels(app_config_get):
        return list(_resolve_supplement_allowlist_paths(app_config_get))

    paths: list[str] = []
    seen: set[str] = set()

    def add(path: str | None) -> None:
        if not path:
            return
        abspath = os.path.abspath(path)
        if not os.path.isfile(abspath) or abspath in seen:
            return
        seen.add(abspath)
        paths.append(abspath)

    if follow_engine:
        add(_classifier_engine_allowlist_path(app_config_get))
    else:
        add(_resolve_configured_allowlist_path(app_config_get))
    for sup in _resolve_supplement_allowlist_paths(app_config_get):
        add(sup)
    if not paths:
        add(_resolve_configured_allowlist_path(app_config_get))
    return paths


def resolve_allowlist_path(app_config_get) -> str | None:
    """Первичный файл allowlist (обратная совместимость)."""
    paths = resolve_all_allowlist_paths(app_config_get)
    return paths[0] if paths else None


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


def _norm_keys_from_label_lines(lines: tuple[str, ...] | list[str]) -> set[str]:
    keys: set[str] = set()
    for raw in lines:
        line = str(raw).split("#", 1)[0].strip()
        if not line:
            continue
        keys.add(_norm_key(line))
        pair = _split_scientific_common_display(line)
        if pair:
            keys.add(_norm_key(pair[0]))
            keys.add(_norm_key(pair[1]))
    return keys


def load_catalog_allowlist_norm_keys(app_config_get) -> frozenset[str] | None:
    """Нормализованные ключи allowlist = активный классификатор (+ extras), не union YOLO EU."""
    follow_engine = str(
        app_config_get("species.catalog_allowlist_follow_classifier_engine", True)
    ).strip().lower() in ("1", "true", "yes", "on")
    if follow_engine and _catalog_use_active_classifier_labels(app_config_get):
        labels = load_active_classifier_label_names(app_config_get)
        if labels:
            keys = _norm_keys_from_label_lines(labels)
            for extra in _catalog_allowlist_extra_names(app_config_get):
                keys.add(_norm_key(extra))
            return frozenset(keys)

    paths = resolve_all_allowlist_paths(app_config_get)
    if not paths:
        extras = _catalog_allowlist_extra_names(app_config_get)
        if not extras:
            return None
        return frozenset(_norm_key(n) for n in extras)
    keys: set[str] = set()
    for path in paths:
        keys |= set(_load_allowlist_norm_keys_cached(path))
    for extra in _catalog_allowlist_extra_names(app_config_get):
        keys.add(_norm_key(extra))
    return frozenset(keys)


def clear_allowlist_cache() -> None:
    """Очистить lru_cache загрузки allowlist (после смене файла или конфига)."""
    _load_allowlist_norm_keys_cached.cache_clear()
    _load_allowlist_names_cached.cache_clear()
    _load_efficientnet_id2label_cached.cache_clear()
    try:
        from services.species_catalog.vocabulary import clear_species_vocabulary_cache

        clear_species_vocabulary_cache()
    except ImportError:
        pass


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
    """Список имён классов активного классификатора + extras (дедуп по norm key)."""
    follow_engine = str(
        app_config_get("species.catalog_allowlist_follow_classifier_engine", True)
    ).strip().lower() in ("1", "true", "yes", "on")
    extras = _catalog_allowlist_extra_names(app_config_get)
    names: list[str] = []
    seen: set[str] = set()

    def add_line(raw: str) -> None:
        nk = _norm_key(raw)
        if nk and nk not in seen:
            names.append(raw)
            seen.add(nk)

    if follow_engine and _catalog_use_active_classifier_labels(app_config_get):
        for raw in load_active_classifier_label_names(app_config_get) or ():
            add_line(raw)
        for extra in extras:
            add_line(extra)
        return tuple(names) if names else None

    paths = resolve_all_allowlist_paths(app_config_get)
    if not paths and not extras:
        return None
    for path in paths:
        for raw in _load_allowlist_names_cached(path):
            add_line(raw)
    for extra in extras:
        add_line(extra)
    return tuple(names) if names else None


def scientific_name_from_canonical_mapping(
    display_name: str,
    mapping: dict[str, str] | None = None,
) -> str | None:
    """Бином из строки mapping ``Scientific (Common)|Canonical`` при совпадении common name."""
    if not (display_name or "").strip():
        return None
    mapping = mapping or load_species_canonical_mapping()
    target_keys = species_name_match_norm_keys(display_name, mapping)
    if not target_keys:
        return None
    for variant, canonical in mapping.items():
        if not (variant or "").strip() or not (canonical or "").strip():
            continue
        if not (species_name_match_norm_keys(canonical, mapping) & target_keys):
            continue
        pair = _split_scientific_common_display(str(variant).strip())
        if pair:
            return pair[0].strip()
    return None


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
    for raw in load_catalog_allowlist_names(app_config_get) or ():
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


__all__ = [
    "allowlist_scientific_name_for_display_name",
    "scientific_name_from_canonical_mapping",
    "catalog_classifier_meta",
    "clear_allowlist_cache",
    "ingest_name_matches_allowlist",
    "load_active_classifier_label_names",
    "load_catalog_allowlist_names",
    "load_catalog_allowlist_norm_keys",
    "resolve_all_allowlist_paths",
    "resolve_allowlist_path",
    "species_matches_allowlist",
    "species_name_match_norm_keys",
]
