#!/usr/bin/env python3
"""Rewrite host-specific /home/.../BirdLense/app paths to container /app/ in JSON artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_HOST_APP_RE = re.compile(
    r"/home/[^/]+/BirdLense/app/",
    re.IGNORECASE,
)


def _fix_value(val: str) -> str:
    return _HOST_APP_RE.sub("/app/", val)


def _walk(obj):
    if isinstance(obj, dict):
        return {k: _walk(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(v) for v in obj]
    if isinstance(obj, str) and "/home/" in obj and "BirdLense/app/" in obj.replace("\\", "/"):
        return _fix_value(obj)
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--glob", default="**/*.json")
    args = ap.parse_args()

    changed = 0
    for path in sorted(args.root.glob(args.glob)):
        if "node_modules" in path.parts or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "/home/" not in text or "BirdLense/app/" not in text.replace("\\", "/"):
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        new_data = _walk(data)
        new_text = json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
        if new_text != text:
            changed += 1
            print(path)
            if not args.dry_run:
                path.write_text(new_text, encoding="utf-8")
    print(json.dumps({"files_changed": changed, "dry_run": args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
