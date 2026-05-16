#!/usr/bin/env python3
"""
Импорт **Caltech-UCSD Birds-200-2011** (CUB) в дерево ``binary/birds`` для
``merge_datasets_three_class.py``: один класс YOLO ``0`` (птица), нормализованные боксы.

Распакуйте официальный архив так, чтобы ``--cub-root`` указывал на корень с подкаталогом
``images/`` и файлами ``bounding_boxes.txt``, ``images.txt``, ``train_test_split.txt``.
Желательно также ``image_sizes.txt`` (быстрее, без чтения каждого JPEG).

Условия использования и загрузка: http://www.vision.caltech.edu/datasets/cub_200_2011/

Сплит: строки ``train_test_split.txt`` с ``is_training_image=1`` → ``train/``,
с ``0`` → ``val/`` (как в Birds-YOLO / многих работах: тест CUB как hold-out val).

Пример::

    cd scripts/datasets
    python3 convert_cub_to_yolo.py \\
      --root ../../datasets/new/detector \\
      --cub-root ~/data/CUB_200_2011

Дальше из корня репозитория: ``make dataset-merge-three-class``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _binary(root: Path) -> Path:
    return root / "binary"


def _ensure_bird_layout(root: Path) -> None:
    base = _binary(root) / "birds"
    for split in ("train", "val"):
        (base / split / "images").mkdir(parents=True, exist_ok=True)
        (base / split / "labels").mkdir(parents=True, exist_ok=True)


def _load_int_map(path: Path) -> dict[int, tuple[int, ...]]:
    """Строки: ``id rest...`` — парсим ведущий int и остальные поля как ints."""
    out: dict[int, tuple[int, ...]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        iid = int(parts[0])
        rest = tuple(int(float(x)) for x in parts[1:])
        out[iid] = rest
    return out


def _load_images_txt(path: Path) -> dict[int, str]:
    """``images.txt``: ``<id> <relative path>``."""
    out: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        iid_str, rel = line.split(None, 1)
        out[int(iid_str)] = rel.strip()
    return out


def _load_train_test(path: Path) -> dict[int, bool]:
    """``train_test_split.txt``: ``<id> <0|1>`` — 1 = train."""
    out: dict[int, bool] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        iid = int(parts[0])
        out[iid] = bool(int(parts[1]))
    return out


def _yolo_line_from_bbox(
    x: float,
    y: float,
    w: float,
    h: float,
    img_w: int,
    img_h: int,
) -> str | None:
    if img_w <= 0 or img_h <= 0 or w <= 0 or h <= 0:
        return None
    xc = (x + w / 2.0) / img_w
    yc = (y + h / 2.0) / img_h
    nw = w / img_w
    nh = h / img_h
    xc = min(1.0, max(0.0, xc))
    yc = min(1.0, max(0.0, yc))
    nw = min(1.0, max(1e-6, nw))
    nh = min(1.0, max(1e-6, nh))
    if xc - nw / 2 < 0 or xc + nw / 2 > 1 or yc - nh / 2 < 0 or yc + nh / 2 > 1:
        # частично вне кадра — подрезаем до пересечения с [0,1]
        x1 = max(0.0, xc - nw / 2)
        y1 = max(0.0, yc - nh / 2)
        x2 = min(1.0, xc + nw / 2)
        y2 = min(1.0, yc + nh / 2)
        nw2 = x2 - x1
        nh2 = y2 - y1
        if nw2 <= 1e-6 or nh2 <= 1e-6:
            return None
        xc = (x1 + x2) / 2.0
        yc = (y1 + y2) / 2.0
        nw, nh = nw2, nh2
    return f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "datasets" / "new" / "detector",
        help="Корень ETL (родитель binary/birds); совпадает с make bootstrap-detector-data",
    )
    ap.add_argument(
        "--cub-root",
        type=Path,
        required=True,
        help="Корень CUB_200_2011 (images/, bounding_boxes.txt, …)",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    cub = args.cub_root.resolve()

    req = [
        cub / "images.txt",
        cub / "bounding_boxes.txt",
        cub / "train_test_split.txt",
    ]
    missing = [p for p in req if not p.is_file()]
    if missing:
        print("Не найдены обязательные файлы CUB:", file=sys.stderr)
        for p in missing:
            print(f"  {p}", file=sys.stderr)
        return 2

    sizes_path = cub / "image_sizes.txt"
    sizes: dict[int, tuple[int, ...]] = {}
    if sizes_path.is_file():
        sizes = _load_int_map(sizes_path)
        # ожидаем (w, h) на каждый id
    else:
        print(
            "[cub] нет image_sizes.txt — будут открываться изображения (установите Pillow: pip install Pillow)",
            file=sys.stderr,
        )

    images_map = _load_images_txt(cub / "images.txt")
    boxes_raw = _load_int_map(cub / "bounding_boxes.txt")
    train_map = _load_train_test(cub / "train_test_split.txt")

    _ensure_bird_layout(root)
    birds_base = _binary(root) / "birds"

    copied_train = 0
    copied_val = 0
    skipped = 0
    pil_warned = False

    for iid in sorted(images_map.keys()):
        rel = images_map[iid]
        src = cub / "images" / rel
        if not src.is_file():
            skipped += 1
            continue
        if iid not in boxes_raw or len(boxes_raw[iid]) < 4:
            skipped += 1
            continue
        bx, by, bw, bh = (float(boxes_raw[iid][j]) for j in range(4))
        if iid not in train_map:
            skipped += 1
            continue
        is_train = train_map[iid]
        split = "train" if is_train else "val"

        img_w: int | None = None
        img_h: int | None = None
        if iid in sizes and len(sizes[iid]) >= 2:
            img_w, img_h = sizes[iid][0], sizes[iid][1]
        else:
            try:
                from PIL import Image  # type: ignore[import-untyped]

                with Image.open(src) as im:
                    img_w, img_h = im.size
            except ImportError:
                if not pil_warned:
                    print(
                        "[cub] нужен image_sizes.txt или пакет Pillow для размеров изображений",
                        file=sys.stderr,
                    )
                    pil_warned = True
                skipped += 1
                continue

        line = _yolo_line_from_bbox(bx, by, bw, bh, img_w, img_h)
        if not line:
            skipped += 1
            continue

        stem = Path(rel).stem
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:80]
        out_name = f"cub_{iid:05d}_{safe}{src.suffix.lower()}"

        dst_img = birds_base / split / "images" / out_name
        dst_lbl = birds_base / split / "labels" / f"{Path(out_name).stem}.txt"

        shutil.copy2(src, dst_img)
        dst_lbl.write_text(line, encoding="utf-8")
        if split == "train":
            copied_train += 1
        else:
            copied_val += 1

    print(
        f"CUB-200-2011 → {birds_base}: train={copied_train} val={copied_val} "
        f"(пропущено {skipped})",
    )
    print("Дальше: make dataset-merge-three-class")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
