#!/usr/bin/env python3
"""Ребаланс binary/birds по источникам (эвристика stem как в report_detector_bird_sources.py).

Сужает перекос CUB/Roboflow в пользу сохранения всего пула COCO+OID и целевых долей wide/feeder.
После — стратифицированное заново разбиение train/val/test.

Пример (репо):
  python3 scripts/datasets/rebalance_detector_bird_binary.py \\
    --root datasets/new/detector --execute

Сначала смотри план без записи (по умолчанию dry-run):
  python3 scripts/datasets/rebalance_detector_bird_binary.py --root datasets/new/detector
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def classify_stem(stem: str) -> str:
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


@dataclass(frozen=True)
class Sample:
    stem: str
    source: str
    rel_image: Path
    rel_label: Path


def collect_samples(birds_root: Path) -> list[Sample]:
    found: list[Sample] = []
    missing = 0
    birds_root = birds_root.resolve()
    for split in ("train", "val", "test"):
        img_dir = birds_root / split / "images"
        lab_dir = birds_root / split / "labels"
        if not img_dir.is_dir():
            continue
        for p in img_dir.rglob("*"):
            if not p.is_file():
                continue
            suf = p.suffix
            if suf.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            stem = p.stem
            lbl = lab_dir / f"{stem}.txt"
            if not lbl.is_file():
                missing += 1
                continue
            ri = p.resolve().relative_to(birds_root)
            rl = lbl.resolve().relative_to(birds_root)
            found.append(
                Sample(
                    stem=stem,
                    source=classify_stem(stem),
                    rel_image=ri,
                    rel_label=rl,
                )
            )
    if missing:
        print(f"[warn] без пары labels/*.txt пропущено изображений: {missing}", flush=True)
    return found


def stratified_split(
    buckets: dict[str, list[Sample]],
    train_f: float,
    val_f: float,
    test_f: float,
    rng: random.Random,
) -> dict[str, list[Sample]]:
    s = train_f + val_f + test_f
    if abs(s - 1.0) > 1e-6:
        raise ValueError("train+val+test must sum to 1")

    out: dict[str, list[Sample]] = {"train": [], "val": [], "test": []}

    for _src, items in buckets.items():
        xs = list(items)
        rng.shuffle(xs)
        n = len(xs)
        if n == 0:
            continue
        nt = int(round(n * train_f))
        nv = int(round(n * val_f))
        nt = min(max(0, nt), n)
        nv = min(max(0, nv), n - nt)
        out["train"].extend(xs[:nt])
        out["val"].extend(xs[nt : nt + nv])
        out["test"].extend(xs[nt + nv :])

    for sp in out:
        rng.shuffle(out[sp])
    return out


def pick_subset(
    samples: list[Sample],
    *,
    min_wide_frac: float,
    feeder_frac_of_total: float,
    rng: random.Random,
) -> tuple[dict[str, list[Sample]], dict[str, int]]:
    """wide = coco+oid (все); roboflow и cub урезаются под целевой размер пачки."""
    wide: list[Sample] = []
    rf: list[Sample] = []
    cub: list[Sample] = []
    other: list[Sample] = []
    for s in samples:
        if s.source in ("coco", "oid_hex16"):
            wide.append(s)
        elif s.source == "roboflow":
            rf.append(s)
        elif s.source == "cub":
            cub.append(s)
        else:
            other.append(s)

    n_w = len(wide)
    if n_w == 0:
        raise SystemExit("нет COCO/OID птиц — сначала bootstrap (make bootstrap-bird-coco-only), иначе детектор останется узкодоменным")

    total_target = max(int(n_w / min_wide_frac), n_w + 1)
    feeder_cap = min(len(rf), int(round(total_target * feeder_frac_of_total)))
    leftover = total_target - n_w - feeder_cap
    leftover = max(0, leftover)
    cub_cap = min(len(cub), leftover)
    rem2 = leftover - cub_cap
    other_cap = min(len(other), max(0, rem2))

    rf_p = rng.sample(rf, feeder_cap) if feeder_cap < len(rf) else rf[:]
    rng.shuffle(cub)
    cub_p = cub[:cub_cap]
    rng.shuffle(other)
    other_p = other[:other_cap]

    counts = {
        "coco": sum(1 for s in wide if s.source == "coco"),
        "oid_hex16": sum(1 for s in wide if s.source == "oid_hex16"),
        "roboflow": len(rf_p),
        "cub": len(cub_p),
        "other": len(other_p),
    }
    by_src: dict[str, list[Sample]] = defaultdict(list)
    for s in wide:
        by_src[s.source].append(s)
    by_src["roboflow"].extend(rf_p)
    by_src["cub"].extend(cub_p)
    for s in other_p:
        by_src[s.source].append(s)

    return dict(by_src), counts


def ensure_unique_stems(split_samples: dict[str, list[Sample]]) -> None:
    seen: set[str] = set()
    dup = 0
    for sp, xs in split_samples.items():
        for s in xs:
            if s.stem in seen:
                dup += 1
            seen.add(s.stem)
    if dup:
        raise RuntimeError(f"stem collision across splits: {dup}")


def write_layout(
    dst_root: Path,
    split_samples: dict[str, list[Sample]],
    *,
    source_root: Path,
    copy: bool,
) -> None:
    for sp, xs in split_samples.items():
        img_out = dst_root / sp / "images"
        lab_out = dst_root / sp / "labels"
        img_out.mkdir(parents=True, exist_ok=True)
        lab_out.mkdir(parents=True, exist_ok=True)
        for s in xs:
            src_img = source_root / s.rel_image
            src_lbl = source_root / s.rel_label
            t_img = img_out / Path(s.rel_image.name)
            t_lbl = lab_out / f"{s.stem}.txt"
            if copy:
                shutil.copy2(src_img, t_img)
                shutil.copy2(src_lbl, t_lbl)
            else:
                shutil.move(str(src_img), str(t_img))
                shutil.move(str(src_lbl), str(t_lbl))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="…/detector (родитель binary/birds)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--min-wide-frac",
        type=float,
        default=0.28,
        metavar="F",
        help="нижняя грань доли (coco+oid) в финальной пачке; остальное — rf+cub+…",
    )
    ap.add_argument(
        "--feeder-frac-of-total",
        type=float,
        default=0.20,
        metavar="F",
        help="до такой доли от итогового T берём roboflow (если хватает кадров)",
    )
    ap.add_argument("--train-frac", type=float, default=0.70)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument(
        "--execute",
        action="store_true",
        help="выполнить (иначе только план JSON в stdout)",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    birds = root / "binary" / "birds"
    if not birds.is_dir():
        raise SystemExit(f"нет каталога {birds}")

    rng = random.Random(args.seed)
    pool = collect_samples(birds)
    if not pool:
        raise SystemExit("пусто — нет пар image+label")

    by_src_before: dict[str, int] = defaultdict(int)
    for s in pool:
        by_src_before[s.source] += 1

    by_src, picked_counts = pick_subset(
        pool,
        min_wide_frac=args.min_wide_frac,
        feeder_frac_of_total=args.feeder_frac_of_total,
        rng=rng,
    )
    split_flat = stratified_split(
        by_src,
        args.train_frac,
        args.val_frac,
        args.test_frac,
        rng,
    )
    ensure_unique_stems(split_flat)

    n_tot = sum(len(v) for v in split_flat.values())
    n_wide = picked_counts["coco"] + picked_counts["oid_hex16"]
    summary = {
        "root": str(root),
        "before_by_source": dict(by_src_before),
        "picked_counts": picked_counts,
        "total_kept": n_tot,
        "wide_frac": round(n_wide / n_tot, 4) if n_tot else 0,
        "per_split": {k: len(v) for k, v in split_flat.items()},
        "params": {
            "min_wide_frac": args.min_wide_frac,
            "feeder_frac_of_total": args.feeder_frac_of_total,
            "train_val_test": [args.train_frac, args.val_frac, args.test_frac],
            "seed": args.seed,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not args.execute:
        print(
            "\nDry-run OK. Чтобы записать новый balanced tree: добавьте --execute "
            "(создаётся backup каталог birds_pre_rebalance_*).",
            flush=True,
        )
        return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / "binary" / f"birds_pre_rebalance_{ts}"
    shutil.move(str(birds), str(backup))
    birds.mkdir(parents=True, exist_ok=False)
    for sp in ("train", "val", "test"):
        (birds / sp / "images").mkdir(parents=True, exist_ok=True)
        (birds / sp / "labels").mkdir(parents=True, exist_ok=True)

    try:
        write_layout(birds, split_flat, source_root=backup, copy=True)
    except Exception:
        shutil.rmtree(birds, ignore_errors=True)
        shutil.move(str(backup), str(birds))
        raise

    print(f"[ok] backup: {backup}", flush=True)
    print(
        "Для отчёта по источникам: make report-detector-bird-sources\n"
        "Дальше добор COCO если wide_frac ниже цели: make bootstrap-bird-coco-only\n"
        "Затем: make dataset-merge-three-class",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
