"""
Канонический ключ вида для слияния BirdNET ↔ видео (общий processor + web).

Порядок: научное имя в hub SQLite → species_taxon.common_name; иначе алиас;
иначе detection.species_mapping + normalize по локализованной строке.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)

_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_processor_src = os.path.join(_root_dir, "processor", "src")
if _processor_src not in sys.path:
    sys.path.insert(0, _processor_src)

from species_normalizer import normalize  # noqa: E402

_lock = threading.Lock()
_cache_mtime: float | None = None
_sci_to_common: dict[str, str] = {}
_alias_to_common: dict[str, str] = {}


def _norm_sci(s: str) -> str:
    t = (s or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _norm_alias_key(s: str) -> str:
    if not s:
        return ""
    x = s.strip().lower()
    x = x.replace("_", " ").replace("-", " ")
    x = re.sub(r"\s+", " ", x)
    return x


def _mapping_value_by_scientific_name(sci_raw: str, species_mapping: dict) -> str | None:
    """
    Найти канон для видео по научному имени в species_mapping.

    Учитываются только ключи вида «Parus major (Great Tit)» — левая часть до «(»
    сравнивается с scientific_name события. Так английский ключ из YAML побеждает
    русский common_name в SQLite (одинаковый лейбл с YOLO/IOC).
    """
    sn = _norm_sci(sci_raw)
    if not sn or not species_mapping:
        return None
    for k, v in species_mapping.items():
        if not isinstance(k, str):
            continue
        ks = k.strip()
        if "(" not in ks:
            continue
        left, _rest = ks.split("(", 1)
        if _norm_sci(left) != sn:
            continue
        if isinstance(v, str):
            out = v.strip()
            return out or None
        if v is not None:
            out = str(v).strip()
            return out or None
    return None


def reset_birdnet_merge_key_cache_for_tests() -> None:
    global _cache_mtime, _sci_to_common, _alias_to_common
    _cache_mtime = None
    _sci_to_common = {}
    _alias_to_common = {}


def _load_sqlite_maps(db_path: str) -> None:
    global _cache_mtime, _sci_to_common, _alias_to_common
    try:
        st = os.stat(db_path)
    except OSError:
        _sci_to_common, _alias_to_common = {}, {}
        _cache_mtime = None
        return
    if _cache_mtime == st.st_mtime:
        return
    sci_map: dict[str, str] = {}
    alias_map: dict[str, str] = {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            for cn, sn in conn.execute(
                "SELECT common_name, scientific_name FROM species_taxon "
                "WHERE scientific_name IS NOT NULL AND trim(scientific_name) != ''"
            ):
                if not cn or not sn:
                    continue
                k = _norm_sci(str(sn))
                if k and k not in sci_map:
                    sci_map[k] = str(cn).strip()
            try:
                rows = conn.execute(
                    "SELECT st.common_name, sa.alias FROM species_alias sa "
                    "JOIN species_taxon st ON st.id = sa.taxon_id"
                )
            except sqlite3.Error:
                rows = []
            for cn, al in rows:
                if not cn or not al:
                    continue
                ak = _norm_alias_key(str(al))
                if ak and ak not in alias_map:
                    alias_map[ak] = str(cn).strip()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.debug("BirdNET merge-key: sqlite read failed %s: %s", db_path, e)
        sci_map, alias_map = {}, {}
    _sci_to_common, _alias_to_common = sci_map, alias_map
    _cache_mtime = st.st_mtime


def sqlite_path_for_birdnet_merge() -> str | None:
    """Путь к hub SQLite или None (PostgreSQL / файла нет). DATA_DIR как у Flask/процессора."""
    url = (os.environ.get("DATABASE_URL") or "").strip().lower()
    if url.startswith("postgresql"):
        return None
    base = (os.environ.get("DATA_DIR") or "data").strip() or "data"
    p = os.path.abspath(os.path.join(base, "db", "birdlense.db"))
    return p if os.path.isfile(p) else None


def birdnet_merge_key(
    ev: dict[str, Any] | None,
    species_mapping: dict,
    db_path: str | None,
) -> str:
    """Имя вида в том же пространстве имён, что и после normalize() для видео-детекций."""
    ev = ev or {}
    loc_raw = str(ev.get("species") or ev.get("common_name") or "").strip()
    loc = "" if loc_raw.lower() in ("unknown", "") else loc_raw

    def _fin(name: str) -> str:
        n = normalize(str(name or "").strip(), species_mapping)
        return "unknown" if n.strip().lower() == "unknown" else n

    sci = ev.get("scientific_name")
    if sci:
        yaml_hit = _mapping_value_by_scientific_name(str(sci), species_mapping)
        if yaml_hit:
            # Строка из YAML уже канон (напр. «Red-breasted Flycatcher»); normalize/_to_title_case
            # портит орнитологические дефисы (Red-Breasted …).
            cleaned = str(yaml_hit).strip()
            return "unknown" if cleaned.lower() == "unknown" else cleaned

    if not db_path or not os.path.isfile(db_path):
        return _fin(loc) if loc else "unknown"

    with _lock:
        _load_sqlite_maps(db_path)

    if sci:
        resolved = _sci_to_common.get(_norm_sci(str(sci)))
        if resolved:
            return _fin(resolved)

    if loc:
        resolved = _alias_to_common.get(_norm_alias_key(loc))
        if resolved:
            return _fin(resolved)
        return _fin(loc)
    return "unknown"
