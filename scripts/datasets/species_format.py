#!/usr/bin/env python3
"""
Формат имён видов: Scientific_name (Common Name).

Используется для слияния датасетов (iNaturalist, birds-525), Frigate, BirdNET.
Единый формат упрощает маппинг и слияние детекций.

Функции:
  - format_scientific_common(scientific, common) -> "Scientific (Common)"
  - parse_scientific_common(s) -> (scientific, common) or None
  - to_folder_name(s) -> безопасное имя папки
  - load_inat_mapping() -> dict common_lower -> "Scientific (Common)"
"""

import re
import urllib.request
from pathlib import Path

INAT_LABELS_URL = "https://raw.githubusercontent.com/google-coral/test_data/master/inat_bird_labels.txt"


def format_scientific_common(scientific: str, common: str) -> str:
    """Собрать строку в формате Scientific (Common)."""
    sci = (scientific or "").strip()
    com = (common or "").strip()
    if not sci and not com:
        return "unknown"
    if not com:
        return sci
    if not sci:
        return com
    return f"{sci} ({com})"


def parse_scientific_common(s: str) -> tuple[str | None, str | None]:
    """
    Разобрать строку формата "Scientific (Common)".
    Возвращает (scientific, common) или (None, None).

    Примеры:
      "Cardinalis cardinalis (Northern Cardinal)" -> ("Cardinalis cardinalis", "Northern Cardinal")
      "Northern Cardinal" -> (None, "Northern Cardinal")
    """
    if not s or not isinstance(s, str):
        return None, None
    s = s.strip()
    if not s:
        return None, None
    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, s


def extract_common_for_lookup(s: str) -> str:
    """
    Извлечь common name для поиска в иерархии/маппинге.
    "Cardinalis cardinalis (Northern Cardinal)" -> "Northern Cardinal"
    "Northern Cardinal" -> "Northern Cardinal"
    """
    _, common = parse_scientific_common(s)
    return common or s


def to_folder_name(s: str) -> str:
    """Безопасное имя папки: пробелы и скобки -> подчёркивания."""
    if not s:
        return "unknown"
    s = re.sub(r"[/\\:*?\"<>|]", "_", s)
    s = s.replace(" ", "_").replace("-", "_").replace("(", "_").replace(")", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown"


def load_inat_mapping(cache_dir: Path | None = None) -> dict[str, str]:
    """
    Загрузить маппинг common_name -> "Scientific (Common)" из inat_bird_labels.txt.
    Ключи в lower case для совпадения без учёта регистра.
    """
    cache_path = None
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / "inat_bird_labels.txt"

    content = None
    if cache_path and cache_path.exists():
        content = cache_path.read_text(encoding="utf-8")
    else:
        try:
            with urllib.request.urlopen(INAT_LABELS_URL, timeout=15) as r:
                content = r.read().decode("utf-8")
            if cache_path:
                cache_path.write_text(content, encoding="utf-8")
        except Exception as e:
            raise SystemExit(f"Failed to fetch inat labels: {e}")

    result = {}
    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Формат inat: "Scientific (Common)"
        sci, com = parse_scientific_common(line)
        if sci and com:
            full = format_scientific_common(sci, com)
            result[com.lower()] = full
            result[com.lower().replace(" ", "_")] = full
        else:
            # Строка без скобок — считаем common
            result[line.lower()] = line
    return result


def common_to_scientific_format(common: str, mapping: dict[str, str] | None = None) -> str:
    """
    Преобразовать common name (или UPPER_SNAKE_CASE) в "Scientific (Common)".
    Возвращает исходную строку, если маппинг не найден.
    """
    mapping = mapping or load_inat_mapping()
    # Common name: "Golden Eagle"
    key = common.lower().replace("_", " ")
    if key in mapping:
        return mapping[key]
    # UPPER_SNAKE: "GOLDEN_EAGLE" -> "Golden Eagle"
    key = common.replace("_", " ").replace("-", " ").title().lower()
    if key in mapping:
        return mapping[key]
    # Прямое совпадение по common
    for k, v in mapping.items():
        if k.replace("_", " ") == key:
            return v
    return common
