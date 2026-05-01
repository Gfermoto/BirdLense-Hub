#!/usr/bin/env python3
"""Импорт Roboflow YOLO (Bird-Feeder и аналоги) в ``binary/birds`` как один класс bird.

В архиве несколько видов птиц (разные class id в ``*.txt``) — все строки переписываются
в класс ``0`` с сохранением bbox (YOLO normalized).

Roboflow обычно кладёт сплит ``valid/`` — он копируется в ``binary/birds/val/``.
Опционально ``test/`` → ``binary/birds/test/`` (чтобы ``merge_datasets_three_class`` видел test).

Имена файлов получают префикс (по умолчанию ``rfbf_``), чтобы не перезаписать кадры из COCO.

Лицензия датасета v6 в карточке Roboflow: CC BY 4.0 — проверьте условия атрибуции перед публикацией весов.

Пример::

    cd scripts/datasets
    python3 import_roboflow_bird_feeder_birds.py \\
        --zip ../../datasets/Bird-Feeder.v6i.yolov11.zip

Затем из корня репозитория: ``make dataset-merge-three-class`` или свой ``--output-dir``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def _remap_lines_to_class_zero(raw: str) -> str:
    out: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            continue
        out.append(f"0 {' '.join(parts[1:])}")
    return "\n".join(out) + ("\n" if out else "")


def _safe_copy_pair(
    img_src: Path,
    lbl_src: Path,
    dst_images: Path,
    dst_labels: Path,
    prefix: str,
) -> bool:
    stem = f"{prefix}{img_src.stem}"
    dst_img = dst_images / f"{stem}{img_src.suffix.lower()}"
    dst_lbl = dst_labels / f"{stem}.txt"
    body = _remap_lines_to_class_zero(lbl_src.read_text(encoding="utf-8", errors="replace"))
    if not body.strip():
        return False
    dst_images.mkdir(parents=True, exist_ok=True)
    dst_labels.mkdir(parents=True, exist_ok=True)
    shutil.copy2(img_src, dst_img)
    dst_lbl.write_text(body, encoding="utf-8")
    return True


def _import_split(
    extracted: Path,
    roboflow_split: str,
    out_split: str,
    birds_root: Path,
    prefix: str,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    """Returns (copied, skipped_no_boxes)."""
    img_dir = extracted / roboflow_split / "images"
    lbl_dir = extracted / roboflow_split / "labels"
    if not img_dir.is_dir() or not lbl_dir.is_dir():
        return 0, 0
    dst_img = birds_root / out_split / "images"
    dst_lbl = birds_root / out_split / "labels"
    copied = 0
    skipped = 0
    for lf in sorted(lbl_dir.glob("*.txt")):
        stem = lf.stem
        img = None
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG"):
            cand = img_dir / f"{stem}{ext}"
            if cand.is_file():
                img = cand
                break
        if img is None:
            skipped += 1
            continue
        raw = lf.read_text(encoding="utf-8", errors="replace")
        if not _remap_lines_to_class_zero(raw).strip():
            skipped += 1
            continue
        if dry_run:
            copied += 1
            continue
        if _safe_copy_pair(img, lf, dst_img, dst_lbl, prefix):
            copied += 1
        else:
            skipped += 1
    return copied, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--zip",
        type=Path,
        required=True,
        help="Путь к ZIP экспорту Roboflow YOLOv11",
    )
    ap.add_argument(
        "--datasets-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Каталог, где лежит scripts/datasets (родитель binary/)",
    )
    ap.add_argument(
        "--prefix",
        type=str,
        default="rfbf_",
        help="Префикс имён файлов в binary/birds",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--no-test",
        action="store_true",
        help="Не импортировать сплит test в binary/birds/test",
    )
    args = ap.parse_args()
    zpath = args.zip.resolve()
    if not zpath.is_file():
        print(f"ZIP not found: {zpath}", file=sys.stderr)
        return 2

    birds_root = args.datasets_root.resolve() / "binary" / "birds"

    total_copied = 0
    total_skip = 0
    mapping = [("train", "train"), ("valid", "val")]
    if not args.no_test:
        mapping.append(("test", "test"))

    with tempfile.TemporaryDirectory(prefix="roboflow_bf_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(tmp_path)

        for rf_split, out_split in mapping:
            c, s = _import_split(
                tmp_path,
                rf_split,
                out_split,
                birds_root,
                args.prefix.strip() or "rfbf_",
                dry_run=args.dry_run,
            )
            print(f"[{rf_split} → birds/{out_split}] copied={c} skipped={s}")
            total_copied += c
            total_skip += s

    action = "Would copy" if args.dry_run else "Copied"
    print(f"{action} {total_copied} bird images (class 0); skipped {total_skip}. Destination: {birds_root}")
    if not args.dry_run:
        print("Next: from repo root → make dataset-merge-three-class (or merge_datasets_three_class.py --output-dir brg)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
