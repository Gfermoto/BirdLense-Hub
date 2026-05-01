#!/usr/bin/env python3
"""Удалить дубликаты изображений в YOLO-датасете (train|val|test)/images по SHA256.

Дубликаты вида ``b_000000000143.jpg`` и ``b_000000000143_1.jpg`` (старый bootstrap с суффиксами;
в актуальном bootstrap такие кадры пропускаются — см. ``_copy_once``).
имеют одинаковые байты — остаётся один файл; соответствующие ``labels/*.txt`` синхронно.

Опционально ``--drop-val-if-in-train``: если тот же хеш есть в train, копии в val удаляются
(снижает утечку train→val).

Пример::

    python3 dedupe_yolo_images.py --root brg
    python3 dedupe_yolo_images.py --root brg --dry-run
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


def _keeper_score(path: Path) -> tuple:
    """Меньше = лучше: без суффикса ``_123`` у stem предпочтительнее."""
    stem = path.stem
    penal = 1 if _STEM_NUM_SUFFIX.search(stem) else 0
    return (penal, stem, path.name)


def _label_path(img: Path) -> Path:
    return img.parent.parent / "labels" / f"{img.stem}.txt"


def _dedupe_split(
    images_dir: Path,
    dataset_root: Path,
    *,
    dry_run: bool,
) -> dict:
    """Внутри одного сплита: один хеш → один файл."""
    removed: list[str] = []
    kept_groups = 0
    if not images_dir.is_dir():
        return {"removed": removed, "duplicate_groups": 0}

    by_hash: dict[str, list[Path]] = defaultdict(list)
    for p in sorted(images_dir.iterdir()):
        if not p.is_file() or p.suffix not in _IMG_EXT:
            continue
        by_hash[_sha256(p)].append(p)

    for digest, paths in by_hash.items():
        if len(paths) <= 1:
            continue
        kept_groups += 1
        keeper = min(paths, key=_keeper_score)
        for p in paths:
            if p == keeper:
                continue
            lbl = _label_path(p)
            removed.append(str(p.relative_to(dataset_root)))
            if not dry_run:
                p.unlink(missing_ok=True)
                lbl.unlink(missing_ok=True)

    return {"removed": removed, "duplicate_groups": kept_groups}


def _cross_split_drop_val(
    root: Path,
    splits: list[str],
    *,
    dry_run: bool,
) -> list[str]:
    """Удалить из val (и др.) изображения, если тот же хеш уже есть в train."""
    hash_to_train: dict[str, Path] = {}
    train_img = root / "train" / "images"
    if train_img.is_dir():
        for p in train_img.iterdir():
            if p.is_file() and p.suffix in _IMG_EXT:
                hash_to_train.setdefault(_sha256(p), p)

    removed: list[str] = []
    for sp in splits:
        if sp == "train":
            continue
        img_dir = root / sp / "images"
        if not img_dir.is_dir():
            continue
        for p in sorted(img_dir.iterdir()):
            if not p.is_file() or p.suffix not in _IMG_EXT:
                continue
            d = _sha256(p)
            if d in hash_to_train:
                tr = hash_to_train[d]
                if p.resolve() == tr.resolve():
                    continue
                removed.append(f"{sp}:{p.name} (same as train/{tr.name})")
                if not dry_run:
                    lbl = _label_path(p)
                    p.unlink(missing_ok=True)
                    lbl.unlink(missing_ok=True)
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path("brg"),
        help="Корень датасета (train|val/images)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Только отчёт, файлы не трогать",
    )
    ap.add_argument(
        "--no-drop-val-if-in-train",
        action="store_false",
        dest="drop_val_if_in_train",
        default=True,
        help="Не удалять val/test, если тот же SHA256 уже есть в train (по умолчанию удаляем)",
    )
    ap.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Куда записать JSON-отчёт (по умолчанию: <root>/dedupe_report.json)",
    )
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    splits = []
    for sp in ("train", "val", "test"):
        if (root / sp / "images").is_dir():
            splits.append(sp)

    report: dict = {"root": str(root), "dry_run": args.dry_run, "per_split": {}, "cross_split_removed": []}

    total_removed = 0
    for sp in splits:
        sub = _dedupe_split(root / sp / "images", root, dry_run=args.dry_run)
        report["per_split"][sp] = sub
        n = len(sub["removed"])
        total_removed += n
        print(f"[{sp}] duplicate groups merged: {sub['duplicate_groups']}, files removed: {n}")

    if args.drop_val_if_in_train:
        xr = _cross_split_drop_val(root, splits, dry_run=args.dry_run)
        report["cross_split_removed"] = xr
        total_removed += len(xr)
        print(f"[cross-split] removed (val/test same bytes as train): {len(xr)}")

    out_report = args.report or (root / "dedupe_report.json")
    if not args.dry_run or args.report:
        out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Report -> {out_report}")

    print(f"Total files removed: {total_removed}" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
