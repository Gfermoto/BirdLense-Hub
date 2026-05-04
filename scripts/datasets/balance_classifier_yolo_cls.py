#!/usr/bin/env python3
# flake8: noqa
"""
Свести YOLO classification dataset к обучаемому профилю (агрессивная усечка охвата видов):

НЕ использовать для цели «максимум европейских птиц» — см. EU_CLASSIFIER.md и
download_birds_eu_merged.py (баланс за счёт новых данных, не выкидывания классов).

1) Удалить классы с суммарным числом изображений < --min-images (по всем сплитам).
2) Ограничить верх: после шага 1 пусть m = min(count). Для каждого класса оставить не более
   m * --max-ratio изображений (равномерное случайное subsample, seed фиксирован).
3) Перераспределить каждый класс по train/val/test с долями --train-frac, --val-frac, --test-frac
   (остаток в train; гарантировать по возможности ≥1 в val и ≥1 в test при n≥3).

После этого имеет смысл прогнать refine_classifier_yolo_cls.py --dedupe-global-only.

Пример:
  python3 scripts/datasets/balance_classifier_yolo_cls.py \\
    --root datasets/new/classifier/yolo_cls \\
    --min-images 40 --max-ratio 3
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _list_images(d: Path) -> list[Path]:
    if not d.is_dir():
        return []
    return sorted(
        p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def _collect_classes(root: Path) -> set[str]:
    names: set[str] = set()
    for split in ("train", "val", "test"):
        sp = root / split
        if not sp.is_dir():
            continue
        for class_dir in sp.iterdir():
            if class_dir.is_dir():
                names.add(class_dir.name)
    return names


def _pool_class(root: Path, class_name: str) -> list[Path]:
    pool: list[Path] = []
    for split in ("train", "val", "test"):
        pool.extend(_list_images(root / split / class_name))
    return pool


def _rmtree_class(root: Path, class_name: str) -> None:
    for split in ("train", "val", "test"):
        d = root / split / class_name
        if d.is_dir():
            shutil.rmtree(d)


def _safe_move(src: Path, dst_dir: Path, used: set[str]) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    name = src.name
    if name in used:
        stem, suf = src.stem, src.suffix
        name = f"{stem}_{hash(src) & 0xFFFFFFFF:x}{suf}"
    used.add(name)
    dst = dst_dir / name
    shutil.move(str(src), str(dst))


def _split_sizes(n: int, tf: float, vf: float, xf: float) -> tuple[int, int, int]:
    """Вернуть (n_train, n_val, n_test), сумма = n."""
    if n <= 0:
        return 0, 0, 0
    if n == 1:
        return 1, 0, 0
    if n == 2:
        return 1, 1, 0
    if n == 3:
        return 1, 1, 1
    nt = max(1, int(round(n * tf)))
    nv = max(1, int(round(n * vf)))
    nx = max(1, int(round(n * xf)))
    arr = [nt, nv, nx]
    while sum(arr) > n:
        mi = max(range(3), key=lambda i: arr[i])
        if arr[mi] > 1:
            arr[mi] -= 1
        else:
            break
    while sum(arr) < n:
        arr[0] += 1
    nt, nv, nx = arr
    assert nt + nv + nx == n
    return nt, nv, nx


def balance_dataset(
    root: Path,
    min_images: int,
    max_ratio: float,
    seed: int,
    train_frac: float,
    val_frac: float,
    test_frac: float,
) -> dict:
    rng = random.Random(seed)
    root = root.resolve()

    all_classes = _collect_classes(root)
    totals = {c: len(_pool_class(root, c)) for c in all_classes}

    dropped = [c for c, t in totals.items() if t < min_images]
    kept = [c for c in all_classes if c not in dropped]

    for c in dropped:
        _rmtree_class(root, c)

    if not kept:
        return {
            "error": "no_classes_remaining",
            "dropped_count": len(dropped),
        }

    totals_kept = {c: len(_pool_class(root, c)) for c in kept}
    m = min(totals_kept.values())
    cap = max(m, int(m * max_ratio))

    placed = 0
    capped_classes = 0

    for c in sorted(kept):
        pool = _pool_class(root, c)
        rng.shuffle(pool)
        if len(pool) > cap:
            pool = pool[:cap]
            capped_classes += 1

        with tempfile.TemporaryDirectory(prefix=f"bl_cls_{c}_") as td:
            st = Path(td)
            staged: list[Path] = []
            for i, p in enumerate(pool):
                dst = st / f"{i:06d}_{p.name}"
                shutil.move(str(p), str(dst))
                staged.append(dst)
            _rmtree_class(root, c)

            n = len(staged)
            nt, nv, nx = _split_sizes(n, train_frac, val_frac, test_frac)
            slices = [
                staged[:nt],
                staged[nt : nt + nv],
                staged[nt + nv :],
            ]
            split_dirs = [root / "train" / c, root / "val" / c, root / "test" / c]
            for split_dir, files in zip(split_dirs, slices):
                used_names: set[str] = set()
                for p in files:
                    _safe_move(p, split_dir, used_names)
                    placed += 1

    # Пустые split-корни ок; убрать пустые классы если где-то обнулилось
    for split in ("train", "val", "test"):
        sp = root / split
        if not sp.is_dir():
            continue
        for class_dir in list(sp.iterdir()):
            if class_dir.is_dir() and not _list_images(class_dir):
                class_dir.rmdir()

    totals_final = {c: len(_pool_class(root, c)) for c in _collect_classes(root)}
    vals = sorted(totals_final.values())
    ratio = round(vals[-1] / max(1, vals[0]), 4) if vals else 0.0

    return {
        "kept_classes": len(totals_final),
        "dropped_classes": len(dropped),
        "min_per_class": vals[0] if vals else 0,
        "max_per_class": vals[-1] if vals else 0,
        "imbalance_max_over_min": ratio,
        "capped_classes": capped_classes,
        "images_placed": placed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--min-images", type=int, default=40)
    ap.add_argument("--max-ratio", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-frac", type=float, default=0.70)
    ap.add_argument("--val-frac", type=float, default=0.20)
    ap.add_argument("--test-frac", type=float, default=0.10)
    ap.add_argument("--report-json", type=Path, default=None)
    args = ap.parse_args()

    s = args.train_frac + args.val_frac + args.test_frac
    if abs(s - 1.0) > 1e-6:
        raise SystemExit(f"train+val+test frac must sum to 1.0, got {s}")

    stats = balance_dataset(
        args.root,
        args.min_images,
        args.max_ratio,
        args.seed,
        args.train_frac,
        args.val_frac,
        args.test_frac,
    )
    stats["root"] = str(args.root.resolve())
    print(json.dumps({"ok": "error" not in stats, **stats}, ensure_ascii=False, indent=2))
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if stats.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
