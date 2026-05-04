#!/usr/bin/env python3
"""
Сводка: сколько изображений на класс в layout YOLO classification (train/val/test).

Помогает найти классы для добора из внешних датасетов (см. CLASSIFIER_EXTRA_SOURCES.md).

  python3 scripts/datasets/report_classifier_class_counts.py \\
    --root datasets/new/classifier/yolo_cls_eu_merged \\
    --below 30 --csv counts.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _count_images(d: Path) -> int:
    if not d.is_dir():
        return 0
    n = 0
    for ext in IMAGE_EXTS:
        n += sum(1 for _ in d.glob(f"*{ext}"))
    return n


def collect_counts(root: Path) -> dict[str, dict[str, int]]:
    root = root.resolve()
    out: dict[str, dict[str, int]] = {}
    for split in ("train", "val", "test"):
        sp = root / split
        if not sp.is_dir():
            continue
        for class_dir in sorted(p for p in sp.iterdir() if p.is_dir()):
            name = class_dir.name
            bucket = out.setdefault(name, {"train": 0, "val": 0, "test": 0})
            bucket[split] += _count_images(class_dir)
    for name in out:
        o = out[name]
        o["total"] = o["train"] + o["val"] + o["test"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--below", type=int, default=None, help="Печатать только классы с total < N")
    ap.add_argument("--csv", type=Path, default=None, help="Записать таблицу в CSV")
    args = ap.parse_args()

    counts = collect_counts(args.root)
    rows = sorted(counts.items(), key=lambda kv: (kv[1]["total"], kv[0]))

    printed = 0
    for name, c in rows:
        total = c["total"]
        if args.below is not None and total >= args.below:
            continue
        print(f"{total:5d}  tr={c['train']:4d} va={c['val']:4d} te={c['test']:4d}  {name}")
        printed += 1

    if args.below is not None:
        print(f"\n(classes with total < {args.below}: {printed})")
    print(f"total distinct classes: {len(rows)}")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["class", "train", "val", "test", "total"])
            for name, c in sorted(rows, key=lambda kv: (-kv[1]["total"], kv[0])):
                w.writerow([name, c["train"], c["val"], c["test"], c["total"]])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
