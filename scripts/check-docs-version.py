#!/usr/bin/env python3
"""Проверяет, что строка версии из VERSION есть в mkdocs.yml (extra.site_version) для баннера в overrides/main.html."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
mk = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
if ver not in mk:
    raise SystemExit(
        f"VERSION={ver!r} не найдена в mkdocs.yml. "
        "Обновите extra.site_version в mkdocs.yml и при необходимости VERSIONING (баннер: overrides/main.html)."
    )
print(f"check-docs-version: OK ({ver} in mkdocs.yml)")
