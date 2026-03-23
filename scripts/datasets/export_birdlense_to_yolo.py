#!/usr/bin/env python3
"""Export BirdLense dataset crops to YOLO classification layout.

Input layout (from BirdLense):
  app/data/dataset/train/<Species Name>/*.jpg

Output layout (YOLO cls):
  <output>/train/<Species Name>/*.jpg
  <output>/val/<Species Name>/*.jpg

This script does not resize or relabel images. It only creates a reproducible
train/val split and copies (or links) files in the expected folder structure.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class ExportStats:
    classes: int
    train_images: int
    val_images: int


def _collect_images(source_dir: Path) -> dict[str, list[Path]]:
    classes: dict[str, list[Path]] = {}
    for class_dir in sorted(source_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        files = [
            p
            for p in sorted(class_dir.iterdir())
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ]
        if files:
            classes[class_dir.name] = files
    return classes


def _safe_unlink(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def _transfer(src: Path, dst: Path, mode: str) -> None:
    if mode == "copy":
        shutil.copy2(src, dst)
        return
    _safe_unlink(dst)
    dst.hardlink_to(src)


def export_dataset(
    source_dir: Path,
    output_dir: Path,
    val_ratio: float,
    seed: int,
    min_images_per_class: int,
    mode: str,
) -> ExportStats:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    classes = _collect_images(source_dir)
    if not classes:
        raise RuntimeError(f"No images found in: {source_dir}")

    rng = random.Random(seed)
    train_total = 0
    val_total = 0
    skipped_classes: list[str] = []

    for split in ("train", "val"):
        (output_dir / split).mkdir(parents=True, exist_ok=True)

    for class_name, images in classes.items():
        if len(images) < min_images_per_class:
            skipped_classes.append(class_name)
            continue

        shuffled = images[:]
        rng.shuffle(shuffled)
        n_val = int(len(shuffled) * val_ratio)
        if len(shuffled) > 1 and val_ratio > 0 and n_val == 0:
            n_val = 1
        if n_val >= len(shuffled):
            n_val = len(shuffled) - 1

        val_images = shuffled[:n_val]
        train_images = shuffled[n_val:]

        train_dir = output_dir / "train" / class_name
        val_dir = output_dir / "val" / class_name
        train_dir.mkdir(parents=True, exist_ok=True)
        val_dir.mkdir(parents=True, exist_ok=True)

        for src in train_images:
            _transfer(src, train_dir / src.name, mode)
        for src in val_images:
            _transfer(src, val_dir / src.name, mode)

        train_total += len(train_images)
        val_total += len(val_images)

    summary = {
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "mode": mode,
        "seed": seed,
        "val_ratio": val_ratio,
        "min_images_per_class": min_images_per_class,
        "classes_total": len(classes),
        "classes_exported": len(classes) - len(skipped_classes),
        "classes_skipped": skipped_classes,
        "train_images": train_total,
        "val_images": val_total,
    }
    (output_dir / "dataset_info.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    class_names = [
        name for name in sorted(classes.keys()) if name not in skipped_classes
    ]
    (output_dir / "classes.txt").write_text(
        "\n".join(class_names) + ("\n" if class_names else ""),
        encoding="utf-8",
    )

    return ExportStats(
        classes=len(class_names),
        train_images=train_total,
        val_images=val_total,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export BirdLense dataset crops to YOLO classification "
            "train/val folders."
        ),
    )
    parser.add_argument(
        "--source",
        default="app/data/dataset/train",
        help="Input classes directory (default: app/data/dataset/train)",
    )
    parser.add_argument(
        "--output",
        default="datasets/birdlense_export",
        help="Output dataset directory (default: datasets/birdlense_export)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.2,
        help="Validation split ratio in [0, 1) (default: 0.2)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic split (default: 42)",
    )
    parser.add_argument(
        "--min-images-per-class",
        type=int,
        default=1,
        help="Skip classes with fewer images than this value (default: 1)",
    )
    parser.add_argument(
        "--mode",
        choices=("copy", "hardlink"),
        default="copy",
        help="How to materialize files in output dataset (default: copy)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if not (0 <= args.val_ratio < 1):
        parser.error("--val-ratio must be in [0, 1)")
    if args.min_images_per_class < 1:
        parser.error("--min-images-per-class must be >= 1")

    source_dir = Path(args.source).resolve()
    output_dir = Path(args.output).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    stats = export_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        val_ratio=args.val_ratio,
        seed=args.seed,
        min_images_per_class=args.min_images_per_class,
        mode=args.mode,
    )

    print(
        "Done: "
        f"classes={stats.classes}, "
        f"train={stats.train_images}, "
        f"val={stats.val_images}, "
        f"output={output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
