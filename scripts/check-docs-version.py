#!/usr/bin/env python3
"""
Проверка согласованности версии релиза с корневым VERSION (issue #120).

Сверяет:
- mkdocs.yml (extra.site_version) — баннер док-сайта;
- app/ui/package.json (version);
- app/web/openapi.yaml (info.version).

Запуск: из корня репозитория: python3 scripts/check-docs-version.py
CI: job docs / openapi-contract при необходимости.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not ver or not re.match(r"^\d+\.\d+\.\d+", ver):
        raise SystemExit(f"VERSION must look like semver (got {ver!r})")

    mk = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    if ver not in mk:
        raise SystemExit(
            f"VERSION={ver!r} не найдена в mkdocs.yml. "
            "Обновите extra.site_version (и при необходимости VERSIONING / overrides/main.html)."
        )

    pkg_path = ROOT / "app" / "ui" / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    pkg_ver = (pkg.get("version") or "").strip()
    if pkg_ver != ver:
        raise SystemExit(
            f"app/ui/package.json version={pkg_ver!r} != VERSION={ver!r}"
        )

    openapi_path = ROOT / "app" / "web" / "openapi.yaml"
    oa = openapi_path.read_text(encoding="utf-8")
    m = re.search(r"(?m)^\s*version:\s*([^\s#]+)", oa)
    if not m:
        raise SystemExit("Не найдено поле version в app/web/openapi.yaml")
    oa_ver = m.group(1).strip().strip('"').strip("'")
    if oa_ver != ver:
        raise SystemExit(
            f"app/web/openapi.yaml version={oa_ver!r} != VERSION={ver!r}"
        )

    print(
        f"check-docs-version: OK (VERSION={ver} sync: mkdocs, package.json, openapi.yaml)"
    )


if __name__ == "__main__":
    main()
