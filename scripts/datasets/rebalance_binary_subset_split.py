#!/usr/bin/env python3
"""Стратифицированное переразбиение train/val/test для одного дерева ``binary/<subdir>/``.

Перемещает пары ``images/*`` + ``labels/<stem>.txt`` (лейбл должен существовать;
для фона допускается пустой ``.txt``).

При дубликатах одного ``stem`` в разных сплитах (типично для фона COCO)
оставляется копия с **большим размером файла**, при равенстве — приоритет
``train`` → ``val`` → ``test``; остальные пары переносятся в
``binary/_quarantine/…``.

Пример (выровнять только фон)::

  python3 rebalance_binary_subset_split.py \\
    --root datasets/new/detector \\
    --subdir background \\
    --train-frac 0.82 --val-frac 0.18
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Sample:
    stem: str
    img: Path
    lbl: Path


def _collect(sub_root: Path) -> list[Sample]:
    found: list[Sample] = []
    for sp in ("train", "val", "test"):
        idir = sub_root / sp / "images"
        ldir = sub_root / sp / "labels"
        if not idir.is_dir() or not ldir.is_dir():
            continue
        for img in sorted(idir.iterdir()):
            if not img.is_file():
                continue
            if img.suffix.lower() not in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".bmp",
            ):
                continue
            st = img.stem
            lbl = ldir / f"{st}.txt"
            if lbl.is_file():
                found.append(Sample(stem=st, img=img, lbl=lbl))
    return found


_SPLIT_RANK = {"train": 0, "val": 1, "test": 2}


def _split_of(sample: Sample) -> str:
    return sample.img.parent.parent.name


def _size_key(sample: Sample) -> tuple[int, int, str]:
    try:
        sz = sample.img.stat().st_size
    except OSError:
        sz = 0
    sp = _split_of(sample)
    rank = _SPLIT_RANK.get(sp, 9)
    return (-sz, rank, str(sample.img))


def dedupe_by_stem(pool: list[Sample]) -> tuple[list[Sample], list[Sample]]:
    """Один ``stem`` → один кадр; остальное (дубликаты между сплитами) — вне пула."""
    by: dict[str, list[Sample]] = defaultdict(list)
    for s in pool:
        by[s.stem].append(s)
    keep: list[Sample] = []
    toss: list[Sample] = []
    for _stem, group in by.items():
        if len(group) == 1:
            keep.append(group[0])
            continue
        group_sorted = sorted(group, key=_size_key)
        keep.append(group_sorted[0])
        toss.extend(group_sorted[1:])
    return keep, toss


def _split_sizes(n: int, train_f: float, val_f: float, test_f: float) -> tuple[int, int, int]:
    s = train_f + val_f + test_f
    if abs(s - 1.0) > 1e-6:
        raise ValueError("train + val + test must sum to 1")
    nv = int(round(n * val_f))
    nte = int(round(n * test_f))
    nv = min(max(0, nv), n)
    nte = min(max(0, nte), n - nv)
    nt = n - nv - nte
    return nt, nv, nte


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Корень ETL (родитель binary/)",
    )
    ap.add_argument(
        "--subdir",
        type=str,
        default="background",
        help="Подкаталог binary/ (birds | rodent | background)",
    )
    ap.add_argument("--train-frac", type=float, default=0.82)
    ap.add_argument("--val-frac", type=float, default=0.18)
    ap.add_argument("--test-frac", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Запретить слияние дубликатов stem (ошибка, если stem встречается >1 раза)",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    sub = args.subdir.strip()
    if sub not in ("birds", "rodent", "background"):
        print("subdir must be birds|rodent|background", file=sys.stderr)
        return 2

    base = root / "binary" / sub
    if not base.is_dir():
        print(f"missing {base}", file=sys.stderr)
        return 2

    pool = _collect(base)
    if not pool:
        print("empty pool", file=sys.stderr)
        return 2

    deduped_to: str | None = None
    dup_count = 0
    if args.no_dedupe:
        stems = [s.stem for s in pool]
        if len(stems) != len(set(stems)):
            print(
                f"duplicate stems: {len(stems) - len(set(stems))} "
                "(уберите --no-dedupe или почистите вручную)",
                file=sys.stderr,
            )
            return 2
    else:
        pool, toss = dedupe_by_stem(pool)
        dup_count = len(toss)
        if dup_count and not args.dry_run:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            qroot = root / "binary" / "_quarantine" / f"{sub}_dup_stems_{ts}"
            for s in toss:
                sp = _split_of(s)
                qimg = qroot / sp / "images" / s.img.name
                qlbl = qroot / sp / "labels" / s.lbl.name
                qimg.parent.mkdir(parents=True, exist_ok=True)
                qlbl.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(s.img), str(qimg))
                shutil.move(str(s.lbl), str(qlbl))
            deduped_to = str(qroot)
        elif dup_count and args.dry_run:
            deduped_to = "(would move to binary/_quarantine/…)"

    if not pool:
        print("empty pool after dedupe", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    rng.shuffle(pool)
    n = len(pool)
    nt, nv, nte = _split_sizes(n, args.train_frac, args.val_frac, args.test_frac)
    chunks: list[tuple[str, list[Sample]]] = [
        ("train", pool[:nt]),
        ("val", pool[nt : nt + nv]),
        ("test", pool[nt + nv :]),
    ]

    moves = 0
    by_sp: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    for dest_sp, samples in chunks:
        for sample in samples:
            cur = sample.img.parent.parent.name
            if cur not in ("train", "val", "test"):
                continue
            by_sp[dest_sp] += 1
            if cur == dest_sp:
                continue
            moves += 1
            if args.dry_run:
                continue
            dst_img = base / dest_sp / "images" / sample.img.name
            dst_lbl = base / dest_sp / "labels" / sample.lbl.name
            dst_img.parent.mkdir(parents=True, exist_ok=True)
            dst_lbl.parent.mkdir(parents=True, exist_ok=True)
            if sample.img.resolve() != dst_img.resolve():
                shutil.move(str(sample.img), str(dst_img))
            if sample.lbl.resolve() != dst_lbl.resolve():
                shutil.move(str(sample.lbl), str(dst_lbl))

    summary = {
        "root": str(root),
        "subdir": sub,
        "total_after_dedupe": len(pool),
        "duplicate_pairs_quarantined": dup_count,
        "quarantine_dupes_dir": deduped_to,
        "target_split_counts": by_sp,
        "cross_split_moves": moves,
        "dry_run": args.dry_run,
        "seed": args.seed,
        "fracs": [args.train_frac, args.val_frac, args.test_frac],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
