#!/usr/bin/env python3
"""
Заполняет три каталога под ``merge_datasets_three_class.py``:

  birds_binary_yolo/   — COCO 2017, только класс ``bird`` → один класс в YOLO (id 0).
  rodent_yolo/         — Open Images V6, класс ``Squirrel`` → один класс (id 0); при слиянии станет Rodent.
  background_yolo/     — COCO train/val: кадры **без** детекции ``bird``, пустые ``.txt``.

Зависимости::

    pip install fiftyone pyyaml

Первый запуск качает выборки через FiftyOne (десятки–сотни МБ при дефолтных лимитах).
Сгенерированные папки с изображениями в git не входят — см. корневой ``.gitignore``.

Пример::

    cd scripts/datasets
    python3 -m venv .venv-detector && . .venv-detector/bin/activate
    pip install fiftyone pyyaml
    python3 bootstrap_detector_yolo.py --birds-train 300 --birds-val 100 \\
        --rodent-train 200 --rodent-val 80 \\
        --background-train 250 --background-val 150

Затем из корня репозитория::

    make dataset-merge-three-class
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def _ensure_layout(root: Path) -> None:
    for sub in ("birds_binary_yolo", "rodent_yolo", "background_yolo"):
        for split in ("train", "val"):
            (root / sub / split / "images").mkdir(parents=True, exist_ok=True)
            (root / sub / split / "labels").mkdir(parents=True, exist_ok=True)


def _detections(sample) -> list:
    """FiftyOne: COCO/OID обычно кладут боксы в ``ground_truth``."""
    gt = getattr(sample, "ground_truth", None)
    if gt is None:
        return []
    return list(gt.detections) if gt.detections else []


def _write_yolo_label(path: Path, class_id: int, detections) -> None:
    lines = []
    for det in detections:
        x, y, w, h = det.bounding_box
        xc = x + w / 2.0
        yc = y + h / 2.0
        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
    path.write_text("".join(lines), encoding="utf-8")


def _unique_copy(src: Path, dst_dir: Path) -> Path:
    """Избегаем коллизий имён между сплитами/источниками."""
    name = src.name
    dst = dst_dir / name
    if not dst.exists():
        shutil.copy2(src, dst)
        return dst
    stem, suf = Path(name).stem, Path(name).suffix
    for i in range(1, 10_000):
        alt = dst_dir / f"{stem}_{i}{suf}"
        if not alt.exists():
            shutil.copy2(src, alt)
            return alt
    raise OSError("too many name collisions")


def _bootstrap_birds(root: Path, train_max: int, val_max: int) -> None:
    import fiftyone as fo
    import fiftyone.zoo as foz

    for split_name, lim, tag in (
        ("train", train_max, "train"),
        ("validation", val_max, "val"),
    ):
        images_dir = root / "birds_binary_yolo" / tag / "images"
        labels_dir = root / "birds_binary_yolo" / tag / "labels"
        print(f"[birds] COCO 2017 {split_name}, class bird, max_samples={lim} …")
        ds = foz.load_zoo_dataset(
            "coco-2017",
            split=split_name,
            label_types=["detections"],
            classes=["bird"],
            max_samples=lim,
        )
        n = 0
        for sample in ds:
            birds = [d for d in _detections(sample) if d.label == "bird"]
            if not birds:
                continue
            dst_img = _unique_copy(Path(sample.filepath), images_dir)
            stem = dst_img.stem
            _write_yolo_label(labels_dir / f"{stem}.txt", 0, birds)
            n += 1
        fo.delete_dataset(ds.name)
        print(f"[birds] → {tag}/: {n} images")


def _bootstrap_rodents(root: Path, train_max: int, val_max: int) -> None:
    import fiftyone as fo
    import fiftyone.zoo as foz

    for split_name, lim, tag in (
        ("train", train_max, "train"),
        ("validation", val_max, "val"),
    ):
        images_dir = root / "rodent_yolo" / tag / "images"
        labels_dir = root / "rodent_yolo" / tag / "labels"
        print(f"[rodent] Open Images V6 {split_name}, Squirrel, max_samples={lim} …")
        ds = foz.load_zoo_dataset(
            "open-images-v6",
            split=split_name,
            label_types=["detections"],
            classes=["Squirrel"],
            max_samples=lim,
            only_matching=True,
        )
        n = 0
        for sample in ds:
            sq = [d for d in _detections(sample) if d.label == "Squirrel"]
            if not sq:
                continue
            dst_img = _unique_copy(Path(sample.filepath), images_dir)
            stem = dst_img.stem
            _write_yolo_label(labels_dir / f"{stem}.txt", 0, sq)
            n += 1
        fo.delete_dataset(ds.name)
        print(f"[rodent] → {tag}/: {n} images")


def _collect_no_bird_background(
    root: Path,
    *,
    coco_split: str,
    pool: int,
    target: int,
    out_tag: str,
) -> int:
    import fiftyone as fo
    import fiftyone.zoo as foz

    images_dir = root / "background_yolo" / out_tag / "images"
    labels_dir = root / "background_yolo" / out_tag / "labels"
    print(f"[background] COCO {coco_split}, scan ≤{pool} samples, need {target} without bird → {out_tag}/ …")
    ds = foz.load_zoo_dataset(
        "coco-2017",
        split=coco_split,
        label_types=["detections"],
        max_samples=pool,
    )
    n = 0
    for sample in ds:
        has_bird = any(d.label == "bird" for d in _detections(sample))
        if has_bird:
            continue
        dst_img = _unique_copy(Path(sample.filepath), images_dir)
        stem = dst_img.stem
        (labels_dir / f"{stem}.txt").write_text("", encoding="utf-8")
        n += 1
        if n >= target:
            break
    fo.delete_dataset(ds.name)
    print(f"[background] → {out_tag}/: {n} images (empty labels)")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Корень выхода (по умолчанию scripts/datasets)",
    )
    ap.add_argument("--birds-train", type=int, default=400)
    ap.add_argument("--birds-val", type=int, default=120)
    ap.add_argument("--rodent-train", type=int, default=300)
    ap.add_argument("--rodent-val", type=int, default=80)
    ap.add_argument("--background-train", type=int, default=280)
    ap.add_argument("--background-val", type=int, default=120)
    ap.add_argument("--background-train-pool", type=int, default=12000, help="Сколько кадров COCO train просмотреть")
    ap.add_argument("--background-val-pool", type=int, default=8000, help="Сколько кадров COCO val просмотреть")
    ap.add_argument("--skip-birds", action="store_true")
    ap.add_argument("--skip-rodents", action="store_true")
    ap.add_argument("--skip-background", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    try:
        import fiftyone as fo  # noqa: F401
        import fiftyone.zoo as foz  # noqa: F401
    except ImportError:
        print("Установите: pip install fiftyone", file=sys.stderr)
        return 2

    _ensure_layout(root)

    if not args.skip_birds:
        _bootstrap_birds(root, args.birds_train, args.birds_val)
    if not args.skip_rodents:
        _bootstrap_rodents(root, args.rodent_train, args.rodent_val)
    if not args.skip_background:
        _collect_no_bird_background(
            root,
            coco_split="train",
            pool=args.background_train_pool,
            target=args.background_train,
            out_tag="train",
        )
        _collect_no_bird_background(
            root,
            coco_split="validation",
            pool=args.background_val_pool,
            target=args.background_val,
            out_tag="val",
        )

    print("\nГотово. Дальше из корня репозитория: make dataset-merge-three-class")
    print(f"Каталоги: {root}/birds_binary_yolo, {root}/rodent_yolo, {root}/background_yolo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
