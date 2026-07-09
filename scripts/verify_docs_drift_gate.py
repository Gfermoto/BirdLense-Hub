#!/usr/bin/env python3
"""Verify documentation drift CI gate contract (#542)."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
MKDOCS = REPO / "mkdocs.yml"
INVENTORY = REPO / "docs" / "_meta" / "docs_inventory.csv"
REDIRECT_SNIPPET = REPO / "docs" / "_meta" / "redirect_maps.yml"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_nav_paths(mkdocs_text: str) -> set[str]:
    nav_section: list[str] = []
    in_nav = False
    for raw in mkdocs_text.splitlines():
        if raw.startswith("nav:"):
            in_nav = True
            continue
        if in_nav and raw and not raw.startswith(" "):
            break
        if in_nav:
            nav_section.append(raw)
    paths: set[str] = set()
    path_re = re.compile(r":\s*([A-Za-z0-9_./-]+\.md)\s*$")
    for row in nav_section:
        m = path_re.search(row)
        if m:
            paths.add(m.group(1))
    return paths


def _parse_redirect_map(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    pair_re = re.compile(r"'([^']+)'\s*:\s*'([^']+)'")
    for raw in text.splitlines():
        m = pair_re.search(raw)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _read_inventory(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: str(v or "").strip() for k, v in row.items()})
    return rows


def evaluate_docs_drift(
    *,
    nav_paths: set[str],
    redirects_mkdocs: dict[str, str],
    redirects_snippet: dict[str, str],
    inventory_rows: list[dict[str, str]],
) -> dict[str, Any]:
    keep_paths = {
        row.get("path", "").removeprefix("docs/")
        for row in inventory_rows
        if row.get("status") == "keep"
    }
    redirect_inventory_paths = {
        Path(row.get("path", "")).name
        for row in inventory_rows
        if row.get("status") in ("redirect-stub", "keep")
        and row.get("path", "").startswith("docs/")
        and Path(row.get("path", "")).name.endswith(".md")
    }
    missing_nav_inventory = sorted(p for p in nav_paths if p not in keep_paths)
    missing_redirect_inventory = sorted(
        p
        for p in redirects_mkdocs.keys()
        if p.endswith(".md") and p not in redirect_inventory_paths
    )
    snippet_drift = {
        key: value
        for key, value in redirects_snippet.items()
        if redirects_mkdocs.get(key) != value
    }
    missing_keep_files: list[str] = []
    for row in inventory_rows:
        if row.get("status") != "keep":
            continue
        rel = row.get("path", "")
        if not rel:
            continue
        if not (REPO / rel).is_file():
            missing_keep_files.append(rel)
    checks = {
        "nav_inventory_sync_ok": len(missing_nav_inventory) == 0,
        "redirect_inventory_sync_ok": len(missing_redirect_inventory) == 0,
        "redirect_snippet_sync_ok": len(snippet_drift) == 0,
        "inventory_keep_files_exist_ok": len(missing_keep_files) == 0,
    }
    ok = all(checks.values())
    return {
        "schema": "docs_drift_gate@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "drift": {
            "missing_nav_inventory": missing_nav_inventory,
            "missing_redirect_inventory": missing_redirect_inventory,
            "redirect_snippet_drift": snippet_drift,
            "missing_keep_files": missing_keep_files,
        },
        "ok": bool(ok),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# Docs Drift Gate Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            (
                "- nav_inventory_sync_ok: "
                f"`{checks.get('nav_inventory_sync_ok')}`"
            ),
            (
                "- redirect_inventory_sync_ok: "
                f"`{checks.get('redirect_inventory_sync_ok')}`"
            ),
            (
                "- redirect_snippet_sync_ok: "
                f"`{checks.get('redirect_snippet_sync_ok')}`"
            ),
            (
                "- inventory_keep_files_exist_ok: "
                f"`{checks.get('inventory_keep_files_exist_ok')}`"
            ),
            (
                "- missing_nav_inventory: "
                f"`{len(drift.get('missing_nav_inventory') or [])}`"
            ),
            (
                "- missing_redirect_inventory: "
                f"`{len(drift.get('missing_redirect_inventory') or [])}`"
            ),
            (
                "- missing_keep_files: "
                f"`{len(drift.get('missing_keep_files') or [])}`"
            ),
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-json",
        default="docs/reports/docs_drift/docs_drift_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/docs_drift/docs_drift_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    mkdocs_text = _read_text(MKDOCS)
    report = evaluate_docs_drift(
        nav_paths=_parse_nav_paths(mkdocs_text),
        redirects_mkdocs=_parse_redirect_map(mkdocs_text),
        redirects_snippet=_parse_redirect_map(_read_text(REDIRECT_SNIPPET)),
        inventory_rows=_read_inventory(INVENTORY),
    )
    out_json = Path(args.out_json).expanduser()
    if not out_json.is_absolute():
        out_json = REPO / out_json
    out_md = Path(args.out_md).expanduser()
    if not out_md.is_absolute():
        out_md = REPO / out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_to_md(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
