#!/usr/bin/env python3
"""Fast YOLO label sanity check for detector datasets (#368)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_labels(labels_dir: Path, *, class_count: int) -> dict:
    errors: list[str] = []
    files = sorted(labels_dir.rglob("*.txt")) if labels_dir.exists() else []
    if not labels_dir.exists():
        errors.append(f"labels_dir not found: {labels_dir}")
    for path in files:
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            cols = line.split()
            if len(cols) != 5:
                errors.append(f"{path}:{lineno}: expected 5 columns")
                continue
            try:
                cls = int(float(cols[0]))
                x, y, w, h = [float(v) for v in cols[1:]]
            except ValueError:
                errors.append(f"{path}:{lineno}: non-numeric value")
                continue
            if cls < 0 or cls >= class_count:
                errors.append(f"{path}:{lineno}: class outside 0..{class_count - 1}")
            if any(v < 0.0 or v > 1.0 for v in (x, y, w, h)):
                errors.append(f"{path}:{lineno}: bbox values must be normalized 0..1")
            if w <= 0.0 or h <= 0.0:
                errors.append(f"{path}:{lineno}: width/height must be > 0")
    return {
        "schema": "yolo_labels_validation@v1",
        "labels_dir": str(labels_dir),
        "label_files": len(files),
        "class_count": class_count,
        "error_count": len(errors),
        "errors": errors[:200],
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels_dir", type=Path)
    parser.add_argument("--class-count", type=int, required=True)
    args = parser.parse_args()
    report = validate_labels(args.labels_dir, class_count=args.class_count)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
