#!/usr/bin/env python3
"""Дедуп JPEG в ``datasets/new/detector/binary/`` по SHA256 **внутри каждой папки класса** и сплита.

То есть только ``birds/train/images`` с самим собой, отдельно ``rodent/train/images``, и т.д.
Кросс-класс (один SHA256 в birds и rodent) **не трогаем**: при конфликте меток это данные для ручного
разбора, а не автоматическое удаление.

Приоритет внутри папки: имя без числового суффикса ``_123`` у stem предпочтительнее.

Удаляются лишние ``images/*.jpg`` и соответствующие ``labels/*.txt``.

Пример::

    python3 dedupe_detector_binary_layout.py --root datasets/new/detector
    python3 dedupe_detector_binary_layout.py --root datasets/new/detector --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"}
_STEM_NUM_SUFFIX = re.compile(r"_\d+$")

def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _label_path(img: Path) -> Path:
    return img.parent.parent / "labels" / f"{img.stem}.txt"


def _keeper_key_intra(path: Path) -> tuple:
    stem = path.stem
    penal = 1 if _STEM_NUM_SUFFIX.search(stem) else 0
    return (penal, stem, path.name)


def dedupe_class_split(
    detector_root: Path,
    cls_name: str,
    split: str,
    *,
    dry_run: bool,
) -> dict:
    imdir = detector_root / "binary" / cls_name / split / "images"
    removed: list[str] = []
    groups = 0
    if not imdir.is_dir():
        return {"duplicate_groups": 0, "files_removed": 0, "removed": []}

    by_hash: dict[str, list[Path]] = defaultdict(list)
    for p in sorted(imdir.iterdir()):
        if p.is_file() and p.suffix in _IMG_EXT:
            by_hash[_sha256(p)].append(p)

    for digest, paths in by_hash.items():
        if len(paths) <= 1:
            continue
        groups += 1
        keeper = min(paths, key=_keeper_key_intra)
        for p in paths:
            if p.resolve() == keeper.resolve():
                continue
            removed.append(str(p.relative_to(detector_root)))
            if not dry_run:
                lbl = _label_path(p)
                p.unlink(missing_ok=True)
                lbl.unlink(missing_ok=True)

    return {"duplicate_groups": groups, "files_removed": len(removed), "removed": removed}


def dedupe_split(
    detector_root: Path,
    split: str,
    *,
    dry_run: bool,
) -> dict:
    class_names = ("birds", "rodent", "background")
    removed: list[str] = []
    groups = 0
    per_class: dict[str, dict] = {}
    for cls_name in class_names:
        sub = dedupe_class_split(detector_root, cls_name, split, dry_run=dry_run)
        per_class[cls_name] = sub
        removed.extend(sub["removed"])
        groups += sub["duplicate_groups"]
    return {
        "duplicate_groups": groups,
        "files_removed": len(removed),
        "removed": removed,
        "per_class": per_class,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Корень детектора (внутри есть binary/birds|rodent|background)",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()
    root = args.root.resolve()
    bin_root = root / "binary"
    if not bin_root.is_dir():
        print(f"Нет каталога binary: {bin_root}", file=sys.stderr)
        return 2

    report: dict = {"root": str(root), "dry_run": args.dry_run, "per_split": {}}
    total_removed = 0
    total_groups = 0

    for split in ("train", "val", "test"):
        if not any(
            (root / "binary" / cls / split / "images").is_dir()
            for cls in ("birds", "rodent", "background")
        ):
            continue
        sub = dedupe_split(root, split, dry_run=args.dry_run)
        report["per_split"][split] = sub
        total_removed += sub["files_removed"]
        total_groups += sub["duplicate_groups"]
        print(
            f"[binary {split}] duplicate_groups={sub['duplicate_groups']}, "
            f"removed={sub['files_removed']}"
        )

    report["totals"] = {"duplicate_groups": total_groups, "files_removed": total_removed}
    out = args.report or (root / "binary_dedupe_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report -> {out}")
    print(f"Total removed: {total_removed}" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
