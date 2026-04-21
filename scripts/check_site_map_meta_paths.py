#!/usr/bin/env python3
"""Fail if mkdocs Meta / Repository nav targets are missing from docs/SITE_MAP.md.

Run from repo root after `pip install -r requirements-docs.txt` (needs PyYAML).
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
    site = (ROOT / "docs" / "SITE_MAP.md").read_text(encoding="utf-8")
    meta = _nav_paths("Meta")
    repo = _nav_paths("Repository (canonical files)")
    meta_chunk = _chunk(site, "## Meta (MkDocs sidebar", "## Repository (canonical files)")
    repo_chunk = _chunk(site, "## Repository (canonical files)", "## Russian")
    _check("Meta", meta, meta_chunk)
    _check("Repository", repo, repo_chunk)
    print(f"check_site_map_meta_paths: OK (Meta {len(meta)}, Repository {len(repo)} paths)")


if __name__ == "__main__":
    main()
