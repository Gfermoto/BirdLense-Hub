"""Единая канонизация имён каталога (eBird/Clements-style display names)."""

from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from util import load_species_canonical_mapping, normalize_species_to_canonical

_PROTECTED_SERVICE_NAMES = frozenset(
    {
        "bird",
        "birds",
        "unknown",
        "rodent",
        "squirrel",
    }
)

_GROUP_LABEL_RE = re.compile(
    r"\band\s+allies\b|\band\s+relatives\b|,\s*.+\s+and\s+",
    re.IGNORECASE,
)


def _norm_key(name: str) -> str:
    s = str(name or "").strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", s)


def _hierarchy_seed_path() -> Path:
    return Path(__file__).resolve().parents[2] / "seed" / "hierarchy_names.txt"


@lru_cache(maxsize=1)
def load_hierarchy_parent_child_map() -> dict[str, list[str]]:
    """child -> parent из seed/hierarchy_names.txt."""
    out: dict[str, list[str]] = defaultdict(list)
    path = _hierarchy_seed_path()
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        child, parent = [p.strip() for p in line.split("|", 1)]
        if child and parent:
            out[parent].append(child)
    return dict(out)


@lru_cache(maxsize=1)
def load_hierarchy_taxon_labels() -> frozenset[str]:
    """Имена-узлы иерархии (семейства/группы), не отдельные виды в allowlist."""
    children_by_parent = load_hierarchy_parent_child_map()
    labels: set[str] = set()
    for parent, children in children_by_parent.items():
        if len(children) < 2:
            continue
        labels.add(parent)
    return frozenset(labels)


_LATIN_EPITHET_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _looks_like_latin_scientific_name(text: str) -> bool:
    """``Genus species`` (эпитеты в нижнем регистре), не ``Common Goldeneye``."""
    parts = [p for p in str(text or "").strip().split() if p]
    if len(parts) < 2:
        return False
    if not re.match(r"^[A-Z][a-z]+$", parts[0]):
        return False
    return all(_LATIN_EPITHET_RE.match(p) for p in parts[1:])


def parse_scientific_and_common(name: str) -> tuple[str | None, str]:
    """``Scientific (Common)`` только для латинского бинома; plumage-варианты — целиком."""
    clean = (name or "").strip()
    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", clean)
    if not m:
        return None, clean
    left = m.group(1).strip()
    right = m.group(2).strip()
    if _looks_like_latin_scientific_name(left):
        return left or None, right or clean
    return None, clean


def format_display_casing(value: str) -> str:
    """Title-case только для полностью UPPERCASE строк."""
    clean = " ".join(str(value or "").strip().split())
    if not clean:
        return clean
    if clean.isupper():
        return clean.title()
    return clean


def normalize_catalog_display_name(
    raw_name: str,
    mapping: dict[str, str] | None = None,
) -> str:
    """Каноническое отображаемое имя вида для Species.name."""
    clean = " ".join(str(raw_name or "").strip().split())
    if not clean:
        return clean
    mapping = mapping or load_species_canonical_mapping()
    _sci, common = parse_scientific_and_common(clean)
    base = common or clean
    canonical = normalize_species_to_canonical(base, mapping)
    display = str(canonical).strip() if canonical else base
    return format_display_casing(display)


def is_group_label_heuristic(name: str) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    if _GROUP_LABEL_RE.search(text):
        return True
    if "," in text and " and " in text.lower():
        return True
    return False


def is_hierarchy_taxon_label(
    name: str,
    *,
    allowlist_norm_keys: frozenset[str] | None = None,
    mapping: dict[str, str] | None = None,
) -> bool:
    """True для семейств/групп (не карточка вида в каталоге)."""
    clean = str(name or "").strip()
    if not clean:
        return False
    if _norm_key(clean) in _PROTECTED_SERVICE_NAMES:
        return False
    if allowlist_norm_keys:
        from services.species_catalog.allowlist import species_matches_allowlist

        if species_matches_allowlist(clean, allowlist_norm_keys, mapping or {}):
            return False
    if clean in load_hierarchy_taxon_labels():
        return True
    return is_group_label_heuristic(clean)


def audio_search_term_for_species_name(
    name: str,
    *,
    allowlist_norm_keys: frozenset[str] | None = None,
    mapping: dict[str, str] | None = None,
) -> str:
    """Поисковый термин для Xeno-canto (группы → первый allowlist-потомок)."""
    clean = str(name or "").strip()
    if not clean:
        return ""
    display = normalize_catalog_display_name(clean, mapping)
    if allowlist_norm_keys:
        from services.species_catalog.allowlist import species_matches_allowlist

        is_group = is_hierarchy_taxon_label(
            display,
            allowlist_norm_keys=allowlist_norm_keys,
            mapping=mapping,
        )
        if not is_group and species_matches_allowlist(
            display,
            allowlist_norm_keys,
            mapping or {},
        ):
            _sci, common = parse_scientific_and_common(display)
            return common or display
        children = load_hierarchy_parent_child_map().get(clean) or []
        for child in children:
            child_display = normalize_catalog_display_name(child, mapping)
            if species_matches_allowlist(child_display, allowlist_norm_keys, mapping or {}):
                _sci, common = parse_scientific_and_common(child_display)
                return common or child_display
    _sci, common = parse_scientific_and_common(display)
    return common or display


def is_all_caps_display_name(name: str) -> bool:
    letters = [c for c in str(name or "") if c.isalpha()]
    if len(letters) < 3:
        return False
    return str(name).strip().isupper()


__all__ = [
    "audio_search_term_for_species_name",
    "format_display_casing",
    "is_all_caps_display_name",
    "is_group_label_heuristic",
    "is_hierarchy_taxon_label",
    "load_hierarchy_parent_child_map",
    "load_hierarchy_taxon_labels",
    "normalize_catalog_display_name",
    "parse_scientific_and_common",
]
