#!/usr/bin/env python3
"""Оценка долей источников в binary/birds по эвристике имени файла.

  - coco: stem ровно 12 цифр (выгрузка bootstrap COCO bird)
  - oid_hex16: stem 16 hex-символов (типично Open Images)
  - cub: начинается с cub_
  - roboflow: начинается с rfbf_
  - other: всё прочее

Рекурсивный обход images/ (JPEG). Не судит о качестве боксов.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path


def _classify(stem: str) -> str:
    if len(stem) == 12 and stem.isdigit():
        return "coco"
    if len(stem) == 16:
        try:
            int(stem, 16)
            return "oid_hex16"
        except ValueError:
            pass
    if stem.startswith("cub_"):
        return "cub"
    if stem.startswith("rfbf_"):
        return "roboflow"
    return "other"


def _iter_jpegs(d: Path):
    yield from d.rglob("*.jpg")
    yield from d.rglob("*.jpeg")
    yield from d.rglob("*.JPG")
    yield from d.rglob("*.JPEG")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "datasets/new/detector",
        help="Корень ETL с binary/birds",
    )
    args = ap.parse_args()
    base = args.root.resolve() / "binary" / "birds"
    grand: Counter[str] = Counter()
    splits: dict[str, Counter[str]] = {}

    for split in ("train", "val", "test"):
        c: Counter[str] = Counter()
        img_dir = base / split / "images"
        if img_dir.is_dir():
            for p in _iter_jpegs(img_dir):
                if p.is_file():
                    c[_classify(p.stem)] += 1
        splits[split] = c
        grand += c

    def row(label: str, c: Counter[str]) -> None:
        tot = sum(c.values())
        print(f"{label:16s} total={tot}")
        if tot == 0:
            return
        for k in sorted(c.keys(), key=lambda x: (-c[x], x)):
            print(f"  {k:14s} {c[k]:7d}  {100 * c[k] / tot:5.1f}%")

    print(f"CORR birds: {base}", flush=True)
    for split in ("train", "val", "test"):
        if sum(splits[split].values()):
            row(f"[{split}]", splits[split])
            print("")
    row("[all splits]", grand)
    tot = sum(grand.values())
    if tot:
        coco = grand.get("coco", 0)
        print(f"COCO fraction (train+val heuristic): {100 * coco / tot:.2f}% of all bird JPEG")

    coco_low = sum(grand.get(k, 0) for k in ("coco", "oid_hex16")) / tot if tot else 0
    if tot and coco_low < 0.15:
        print(
            "\nПодсказка: мало широкодоменного COCO/OID среди общей массы; добавьте COCO: "
            "``make bootstrap-bird-coco-only`` или квоты BIRD_COCO_TRAIN/BIRD_COCO_VAL.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
