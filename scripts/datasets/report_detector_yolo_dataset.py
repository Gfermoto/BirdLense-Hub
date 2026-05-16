#!/usr/bin/env python3
# flake8: noqa: E501
"""Отчёт по составу merged YOLO-детектора (после merge_datasets_three_class).

Считает train|val|test/images: префиксы b_/r_/g_ и эвристику источника по имени файла.
Только чтение диска.

Пример: python3 report_detector_yolo_dataset.py --root datasets/new/detector/yolo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"}


def _body(name: str) -> str:
    for pref in ("b_", "r_", "g_"):
        if name.startswith(pref):
            return name[len(pref) :]
    return name


def source_bucket(body: str) -> str:
    bl = body.lower()
    if bl.startswith("hubbg_"):
        return "hub_import (hubbg_)"
    if bl.startswith("rfbf_"):
        return "roboflow_bird_feeder"
    if bl.startswith("cub_"):
        return "cub200"
    if re.match(r"^[0-9]{12}\.jpe?g$", body, re.I):
        return "coco_12digit_name"
    if re.match(r"^[0-9a-f]{16}\.jpe?g$", body, re.I):
        return "open_images_hex16"
    return "other_or_unclassified"


def prefix_class(name: str) -> str:
    if name.startswith("b_"):
        return "Bird (b_)"
    if name.startswith("r_"):
        return "Rodent (r_)"
    if name.startswith("g_"):
        return "Background (g_)"
    return "no_prefix"


def analyze(root: Path) -> dict:
    out: dict = {"root": str(root.resolve()), "splits": {}, "totals": {}}
    grand_by_pre: dict[str, int] = defaultdict(int)
    grand_by_src: dict[str, int] = defaultdict(int)

    for split in ("train", "val", "test"):
        img_dir = root / split / "images"
        if not img_dir.is_dir():
            continue
        by_pre: dict[str, int] = defaultdict(int)
        by_src: dict[str, int] = defaultdict(int)
        n_files = 0
        for p in img_dir.iterdir():
            if not p.is_file() or p.suffix not in _IMG_EXT:
                continue
            n_files += 1
            pre = prefix_class(p.name)
            by_pre[pre] += 1
            src = source_bucket(_body(p.name))
            by_src[src] += 1
            grand_by_pre[pre] += 1
            grand_by_src[src] += 1

        out["splits"][split] = {
            "images_total": n_files,
            "by_merge_prefix": dict(sorted(by_pre.items())),
            "by_source_heuristic": dict(sorted(by_src.items(), key=lambda x: -x[1])),
        }

    out["totals"] = {
        "images_total": sum(grand_by_pre.values()),
        "by_merge_prefix": dict(sorted(grand_by_pre.items())),
        "by_source_heuristic": dict(sorted(grand_by_src.items(), key=lambda x: -x[1])),
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="Корень merged YOLO (с train/images)")
    ap.add_argument("--json-out", type=Path, default=None, help="Записать полный JSON отчёт")
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"Нет каталога: {root}", file=sys.stderr)
        return 2

    rep = analyze(root)

    print(f"ROOT: {rep['root']}")
    print("")
    for sp, block in rep["splits"].items():
        print(f"=== {sp} ===  images: {block['images_total']}")
        print("  по классу (префикс merge):")
        for k, v in block["by_merge_prefix"].items():
            print(f"    {v:6}  {k}")
        print("  по эвристике имени (источник):")
        for k, v in block["by_source_heuristic"].items():
            print(f"    {v:6}  {k}")
        print("")

    t = rep["totals"]
    print("=== ИТОГО по диску ===")
    print(f"  images: {t['images_total']}")
    print("  по классу:")
    for k, v in t["by_merge_prefix"].items():
        print(f"    {v:6}  {k}")
    print("  по источнику (имя файла):")
    for k, v in t["by_source_heuristic"].items():
        print(f"    {v:6}  {k}")

    if args.json_out:
        args.json_out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nJSON -> {args.json_out.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
