#!/usr/bin/env python3
"""
Грызуны из **COCO instances** JSON (в т.ч. экспорты camera traps / LILA) → ``binary/rodent/<split>/``.

Поддерживается один корень изображений: ``images-dir / file_name`` для каждой записи ``images[].file_name``.

Полезно когда Open Images недоступен по объёму: скачанный ZIP/папка бенча + ``instances*.json``.
Дальше: ``make dataset-merge-three-class``.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path


def coco_bbox_pixels_to_yolo_line(
    bbox_xywh: list[float], img_w: int, img_h: int
) -> str | None:
    """Один bbox COCO ``[x,y,w,h]`` пиксели → строка ``0 xc yc w h`` нормализованная."""

    x, y, bw, bh = bbox_xywh
    if bw <= 1 or bh <= 1 or img_w <= 0 or img_h <= 0:
        return None
    xc = (x + bw / 2.0) / img_w
    yc = (y + bh / 2.0) / img_h
    nw = bw / img_w
    nh = bh / img_h
    outs = []
    for v in (xc, yc, nw, nh):
        if v < 0.0 or v > 1.0:
            v = max(0.0, min(1.0, v))
        outs.append(v)
    xc, yc, nw, nh = outs
    return f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n"


def _stem_safe(name: str) -> str:
    base = Path(name).stem
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)[:72]
    return safe or "img"


def _copy_image_once(src: Path, dst_images: Path, prefix: str, image_id: int) -> tuple[Path, str]:
    suf = src.suffix.lower() or ".jpg"
    stem = f"{prefix}{image_id}_{_stem_safe(src.name)}"
    dst = dst_images / f"{stem}{suf}"
    if dst.exists():
        return dst, stem
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst, stem


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path("datasets/new/detector"),
        help="Корень детектора (родитель для binary/)",
    )
    ap.add_argument("--coco-json", type=Path, required=True)
    ap.add_argument(
        "--images-dir",
        type=Path,
        required=True,
        help="Базовый каталог файлов из COCO ``file_name``",
    )
    ap.add_argument("--split", choices=("train", "val"), default="train")
    ap.add_argument(
        "--keywords",
        type=str,
        default="mouse,mice,rat,rats,squirrel,rodent,vole,marmot,gopher,"
        "pika,chipmunk,hamster,porcupine,rabbit,hare,bunny",
        help="Подстроки имён категорий COCO (через запятую), без учёта регистра",
    )
    ap.add_argument(
        "--prefix",
        default="lila_",
        help="Префикс имён файлов (избежать коллизий с OID/COCO bootstrap)",
    )
    ap.add_argument("--max-images", type=int, default=5000, help="0 = без лимита")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Только счётчик, без записи файлов",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    binary = root / "binary"
    images_out = binary / "rodent" / args.split / "images"
    labels_out = binary / "rodent" / args.split / "labels"
    if not args.dry_run:
        images_out.mkdir(parents=True, exist_ok=True)
        labels_out.mkdir(parents=True, exist_ok=True)

    data = json.loads(args.coco_json.read_text(encoding="utf-8"))
    cats = {c["id"]: str(c.get("name", "") or "") for c in data.get("categories", [])}
    kws = [k.strip().lower() for k in args.keywords.split(",") if k.strip()]
    rodent_cat_ids = {
        cid
        for cid, nm in cats.items()
        if any(kw in nm.lower() for kw in kws)
    }
    if not rodent_cat_ids:
        print(
            "[import-coco-rodents] ни одна категория не совпала с keywords "
            f"(cats={len(cats)}). Пример имён: {list(cats.values())[:15]}",
            file=sys.stderr,
        )
        return 2

    anns_raw = data.get("annotations", [])
    by_image: dict[int, list[list[float]]] = {}
    for ann in anns_raw:
        if ann.get("iscrowd", 0):
            continue
        cid = ann.get("category_id")
        if cid not in rodent_cat_ids:
            continue
        bbox = ann.get("bbox")
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or not all(isinstance(z, (int, float)) for z in bbox)
        ):
            continue
        iid = int(ann["image_id"])
        by_image.setdefault(iid, []).append([float(z) for z in bbox])

    id_to_meta: dict[int, tuple[str, int, int]] = {}
    for im in data.get("images", []):
        iid = int(im["id"])
        fn = str(im.get("file_name", "") or "").strip()
        if not fn:
            continue
        w = int(im.get("width", 0))
        h = int(int(im["height"])) if im.get("height") is not None else 0
        id_to_meta[iid] = (fn, w, h)

    paired: list[tuple[int, str, list[list[float]], int, int]] = []
    for iid, boxes in by_image.items():
        if iid not in id_to_meta:
            continue
        fn, cw, ch = id_to_meta[iid]
        if cw <= 0 or ch <= 0:
            continue
        paired.append((iid, fn, boxes, cw, ch))

    rng = random.Random(args.seed)
    rng.shuffle(paired)
    lim = args.max_images
    if lim and lim > 0:
        paired = paired[:lim]

    copied = 0
    skipped = 0
    for iid, fn, boxes, cw, ch in paired:
        src = args.images_dir / fn
        if not src.is_file():
            # иногда относительные пути содержат вложения
            alt = args.images_dir / Path(fn).name
            src = alt if alt.is_file() else src

        lines: list[str] = []
        for bbox in boxes:
            line = coco_bbox_pixels_to_yolo_line(bbox, cw, ch)
            if line:
                lines.append(line)

        if not lines:
            skipped += 1
            continue
        if not src.is_file():
            skipped += 1
            continue

        if args.dry_run:
            copied += 1
            continue

        _, stem = _copy_image_once(src.resolve(), images_out, args.prefix, iid)
        label_path = labels_out / f"{stem}.txt"
        if label_path.exists():
            skipped += 1
            continue
        label_path.write_text("".join(lines), encoding="utf-8")
        copied += 1

    print(
        f"[import-coco-rodents] categories matched: {sorted(cats[c] for c in rodent_cat_ids)} "
        f"| images queued: {len(paired)} | written: {copied} skipped: {skipped} → {images_out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
