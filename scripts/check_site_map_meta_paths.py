#!/usr/bin/env python3
"""Fail if mkdocs nav targets are missing from matching excerpts in docs/SITE_MAP*.md.

English ``nav``: **Use the hub**, **Develop & integrate**, **ML & project**, **Meta**,
**Repository (canonical files)** — checked against ``docs/SITE_MAP.md``.

Russian ``nav`` (flat block **Русский**): partitioned at known boundary filenames and
checked against ``docs/SITE_MAP.ru.md`` (top menu + four sidebar sections).

Run from repo root after ``pip install -r requirements-docs.txt`` (needs PyYAML).
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError as e:
    print(
        "check_site_map_meta_paths: install PyYAML, e.g. pip install -r requirements-docs.txt",
        file=sys.stderr,
    )
    raise SystemExit(2) from e

ROOT = Path(__file__).resolve().parents[1]

_STUB_MARKERS = ("Do not edit this stub", "This page moved")


def _is_redirect_stub(path: Path) -> bool:
    if not path.is_file():
        return True
    text = path.read_text(encoding="utf-8")
    return any(m in text for m in _STUB_MARKERS)

# SITE_MAP.md uses curly quotes in sidebar headings (MkDocs Material style).
_HUB = "## Sidebar — \u201cUse the hub\u201d"
_DEVELOP = "## Sidebar — \u201cDevelop & integrate\u201d"
_ML = "## Sidebar — \u201cML & project\u201d"
_META = "## Meta (MkDocs sidebar"

# SITE_MAP.ru.md — section headings (guillemets « », typographic quotes).
_RU_TOP_START = "## Верхнее меню"
_RU_USE_START = "## Сайдбар — «Использование»"
_RU_DEV_START = "## Сайдбар — «Разработка и интеграции»"
_RU_ML_START = "## Сайдбар — «ML и проект»"
_RU_META_START = "## Мета (боковое меню"
_RU_REPO_START = "## Репозиторий (канонические файлы)"


def _nav_paths(nav_key: str) -> list[str]:
    spec = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    nav = spec["nav"]
    for block in nav:
        if isinstance(block, dict) and nav_key in block:
            out: list[str] = []
            for item in block[nav_key]:
                if isinstance(item, dict):
                    out.extend(v for v in item.values() if isinstance(v, str))
            return out
    raise SystemExit(f"mkdocs.yml: nav key {nav_key!r} not found")


def _partition_russian_nav(paths: list[str]) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Split flat ``Русский`` nav into top / hub / develop / ml / meta by boundary files."""
    if len(paths) < 5:
        raise SystemExit("mkdocs.yml: Русский nav too short")
    if paths[0] != "OVERVIEW.ru.md" or paths[1] != "README.ru.md":
        raise SystemExit(
            "mkdocs.yml: expected Russian nav to start with OVERVIEW.ru.md, README.ru.md"
        )
    try:
        i_arch = paths.index("ARCHITECTURE.ru.md")
        i_train = paths.index("TRAINING.ru.md")
        i_repo = paths.index("REPOSITORY_LAYOUT.ru.md")
    except ValueError as e:
        raise SystemExit(f"mkdocs.yml: Russian nav missing boundary filename: {e}") from e
    top = paths[:2]
    hub = paths[2:i_arch]
    develop = paths[i_arch:i_train]
    ml = paths[i_train:i_repo]
    meta = paths[i_repo:]
    return top, hub, develop, ml, meta


def _chunk(site: str, start_sub: str, end_sub: str) -> str:
    start = site.find(start_sub)
    if start == -1:
        raise SystemExit(f"docs/SITE_MAP.md: substring {start_sub!r} not found")
    end = site.find(end_sub, start + 1)
    if end == -1:
        raise SystemExit(f"docs/SITE_MAP.md: end substring {end_sub!r} not found after {start_sub!r}")
    return site[start:end]


def _check(label: str, paths: list[str], chunk: str) -> None:
    missing = [p for p in paths if p and p not in chunk]
    if missing:
        raise SystemExit(f"{label}: paths from mkdocs.yml not found in SITE_MAP excerpt: {missing}")


def main() -> None:
    site_map = ROOT / "docs" / "SITE_MAP.md"
    site_map_ru = ROOT / "docs" / "SITE_MAP.ru.md"
    if _is_redirect_stub(site_map) or _is_redirect_stub(site_map_ru):
        print(
            "check_site_map_meta_paths: SKIP (docs/SITE_MAP*.md are redirect stubs; "
            "canonical maps: docs/ (see mkdocs.yml nav)"
        )
        return
    if not site_map.exists() or not site_map_ru.exists():
        print("check_site_map_meta_paths: SKIP (docs/SITE_MAP*.md not present)")
        return

    site = site_map.read_text(encoding="utf-8")
    hub = _nav_paths("Use the hub")
    develop = _nav_paths("Develop & integrate")
    ml = _nav_paths("ML & project")
    meta = _nav_paths("Meta")
    repo = _nav_paths("Repository (canonical files)")
    hub_chunk = _chunk(site, _HUB, _DEVELOP)
    develop_chunk = _chunk(site, _DEVELOP, _ML)
    ml_chunk = _chunk(site, _ML, _META)
    meta_chunk = _chunk(site, _META, "## Repository (canonical files)")
    repo_chunk = _chunk(site, "## Repository (canonical files)", "## Russian")
    _check("Use the hub", hub, hub_chunk)
    _check("Develop & integrate", develop, develop_chunk)
    _check("ML & project", ml, ml_chunk)
    _check("Meta", meta, meta_chunk)
    _check("Repository", repo, repo_chunk)

    site_ru = site_map_ru.read_text(encoding="utf-8")
    ru_all = _nav_paths("Русский")
    ru_top, ru_hub, ru_develop, ru_ml, ru_meta = _partition_russian_nav(ru_all)
    top_chunk = _chunk(site_ru, _RU_TOP_START, _RU_USE_START)
    ru_hub_chunk = _chunk(site_ru, _RU_USE_START, _RU_DEV_START)
    ru_develop_chunk = _chunk(site_ru, _RU_DEV_START, _RU_ML_START)
    ru_ml_chunk = _chunk(site_ru, _RU_ML_START, _RU_META_START)
    ru_meta_chunk = _chunk(site_ru, _RU_META_START, _RU_REPO_START)
    _check("RU top nav", ru_top, top_chunk)
    _check("RU Use the hub", ru_hub, ru_hub_chunk)
    _check("RU Develop & integrate", ru_develop, ru_develop_chunk)
    _check("RU ML & project", ru_ml, ru_ml_chunk)
    _check("RU Meta", ru_meta, ru_meta_chunk)

    print(
        "check_site_map_meta_paths: OK (EN: "
        f"hub {len(hub)}, develop {len(develop)}, ml {len(ml)}, meta {len(meta)}, repo {len(repo)}; "
        f"RU: top {len(ru_top)}, hub {len(ru_hub)}, develop {len(ru_develop)}, ml {len(ru_ml)}, meta {len(ru_meta)})"
    )


if __name__ == "__main__":
    main()
