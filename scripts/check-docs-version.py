#!/usr/bin/env python3
"""Проверяет, что строка версии из VERSION встречается в mkdocs.yml (баннер сайта)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
mk = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
if ver not in mk:
    raise SystemExit(
        f"VERSION={ver!r} не найдена в mkdocs.yml. "
        "Обновите theme.announcement и extra.site_version вместе с релизом (см. docs/VERSIONING.md)."
    )
print(f"check-docs-version: OK ({ver} in mkdocs.yml)")
