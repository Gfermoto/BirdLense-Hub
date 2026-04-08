#!/usr/bin/env python3
"""
Добавить на GitHub Project «BirdLense Hub — Roadmap» (project #2 у владельца)
все **открытые** issues репозитория, которых ещё нет на доске.

Запуск из корня репозитория (нужен `gh auth` с правом project):

  python3 scripts/sync-open-issues-to-roadmap-project.py
  python3 scripts/sync-open-issues-to-roadmap-project.py --dry-run

Переменные окружения (опционально):
  ROADMAP_PROJECT_OWNER  — по умолчанию Gfermoto
  ROADMAP_PROJECT_NUMBER — по умолчанию 2
  GITHUB_REPOSITORY      — по умолчанию Gfermoto/BirdLense-Hub
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def _gh_json(argv: list[str]) -> dict | list:
    out = subprocess.check_output(["gh", *argv], text=True)
    return json.loads(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="только показать, что было бы добавлено",
    )
    args = p.parse_args()

    owner = os.environ.get("ROADMAP_PROJECT_OWNER", "Gfermoto")
    proj = os.environ.get("ROADMAP_PROJECT_NUMBER", "2")
    repo = os.environ.get("GITHUB_REPOSITORY", "Gfermoto/BirdLense-Hub")

    items = _gh_json(
        [
            "project",
            "item-list",
            proj,
            "--owner",
            owner,
            "--limit",
            "500",
            "--format",
            "json",
        ]
    )
    if not isinstance(items, dict) or "items" not in items:
        print("unexpected item-list JSON", file=sys.stderr)
        return 1

    on_board: set[int] = set()
    for it in items.get("items", []):
        c = it.get("content") or {}
        num = c.get("number")
        if isinstance(num, int):
            on_board.add(num)

    open_issues = _gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "500",
            "--json",
            "number,title,url",
        ]
    )
    if not isinstance(open_issues, list):
        print("unexpected issue list JSON", file=sys.stderr)
        return 1

    missing = [x for x in open_issues if x["number"] not in on_board]
    if not missing:
        print(f"OK: все открытые issues ({len(open_issues)}) уже на проекте #{proj} ({owner}).")
        return 0

    print(
        f"Нет на доске ({len(missing)} из {len(open_issues)} открытых):",
        file=sys.stderr,
    )
    for x in missing:
        print(f"  #{x['number']} {x.get('title', '')[:72]}", file=sys.stderr)

    if args.dry_run:
        return 0

    for x in missing:
        url = x.get("url")
        if not url:
            print(f"skip #{x['number']}: no url", file=sys.stderr)
            continue
        subprocess.check_call(
            [
                "gh",
                "project",
                "item-add",
                proj,
                "--owner",
                owner,
                "--url",
                url,
            ]
        )
        print(f"added #{x['number']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
