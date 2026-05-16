#!/usr/bin/env python3
"""Импорт CUB в упаковке VOC (ZIP с ``*_images/*.jpg`` + ``*_labels/*.xml``) в ``binary/birds``.

Подходит для архивов вида ``…/cub_200_2011_xml/{train_images,train_labels,valid_images,valid_labels}``.
Один класс YOLO ``0``. Имена: ``cub_<stem>.<ext>``.

Распаковка один раз в ``<root>/raw/cub200_voc_extracted/`` (перезапись: ``--force-extract``).

Пример::

  python3 import_cub_voc_zip_birds.py \\
    --root datasets/new/detector \\
    --zip datasets/new/detector/raw/CUB200.zip
"""

from __future__ import annotations

import argparse
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def _binary(root: Path) -> Path:
    return root / "binary"


def _ensure_layout(root: Path) -> None:
    base = _binary(root) / "birds"
    for sp in ("train", "val", "test"):
        (base / sp / "images").mkdir(parents=True, exist_ok=True)
        (base / sp / "labels").mkdir(parents=True, exist_ok=True)


def _voc_xml_to_yolo(xml_text: str) -> str | None:
    try:
        el = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    size = el.find("size")
    if size is None:
        return None
    w_el, h_el = size.find("width"), size.find("height")
    if w_el is None or h_el is None or not w_el.text or not h_el.text:
        return None
    iw, ih = int(w_el.text), int(h_el.text)
    if iw <= 0 or ih <= 0:
        return None
    lines: list[str] = []
    for obj in el.findall("object"):
        bb = obj.find("bndbox")
        if bb is None:
            continue
        xmin, ymin, xmax, ymax = bb.find("xmin"), bb.find("ymin"), bb.find("xmax"), bb.find("ymax")
        if None in (xmin, ymin, xmax, ymax) or not all(
            x is not None and x.text for x in (xmin, ymin, xmax, ymax)
        ):
            continue
        x1, y1, x2, y2 = (
            float(xmin.text),
            float(ymin.text),
            float(xmax.text),
            float(ymax.text),
        )
        bw, bh = x2 - x1, y2 - y1
        if bw <= 1 or bh <= 1:
            continue
        xc = (x1 + x2) / 2.0 / iw
        yc = (y1 + y2) / 2.0 / ih
        nw = bw / iw
        nh = bh / ih
        xc = min(1.0, max(0.0, xc))
        yc = min(1.0, max(0.0, yc))
        nw = min(1.0, max(1e-6, nw))
        nh = min(1.0, max(1e-6, nh))
        lines.append(f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n")
    if not lines:
        return None
    return "".join(lines)


def _find_xml_root(unpacked: Path) -> Path | None:
    """Директория, где рядом ``train_images`` и ``train_labels``."""
    for train_img in unpacked.rglob("train_images"):
        if not train_img.is_dir():
            continue
        parent = train_img.parent
        if (parent / "train_labels").is_dir() and (parent / "valid_images").is_dir():
            return parent
    return None


def _import_folder(xml_root: Path, detector_root: Path) -> tuple[int, int, int]:
    birds = _binary(detector_root) / "birds"
    tr = va = skipped = 0

    def do_pair(img_dir: Path, lbl_dir: Path, out_sp: str) -> None:
        nonlocal tr, va, skipped
        out_im = birds / out_sp / "images"
        out_lb = birds / out_sp / "labels"
        for img_p in sorted(img_dir.iterdir()):
            if not img_p.is_file() or img_p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            stem = img_p.stem
            xml_p = lbl_dir / f"{stem}.xml"
            if not xml_p.is_file():
                skipped += 1
                continue
            try:
                ytxt = _voc_xml_to_yolo(xml_p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                skipped += 1
                continue
            if not ytxt or not ytxt.strip():
                skipped += 1
                continue
            sfx = img_p.suffix.lower()
            dst_img = out_im / f"cub_{stem}{sfx}"
            dst_lbl = out_lb / f"cub_{stem}.txt"
            shutil.copy2(img_p, dst_img)
            dst_lbl.write_text(ytxt, encoding="utf-8")
            if out_sp == "train":
                tr += 1
            else:
                va += 1

    ti = xml_root / "train_images"
    tl = xml_root / "train_labels"
    vi = xml_root / "valid_images"
    vl = xml_root / "valid_labels"
    if not ti.is_dir() or not tl.is_dir() or not vi.is_dir() or not vl.is_dir():
        print(f"[cub-voc-zip] нет пар папок в {xml_root}", file=sys.stderr)
        return 0, 0, 0
    do_pair(ti, tl, "train")
    do_pair(vi, vl, "val")
    return tr, va, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="Корень ETL …/datasets/new/detector")
    ap.add_argument("--zip", type=Path, required=True, help="Путь к CUB VOC zip")
    ap.add_argument(
        "--force-extract",
        action="store_true",
        help="Удалить ``raw/cub200_voc_extracted`` и заново распаковать ZIP",
    )
    args = ap.parse_args()
    root = args.root.resolve()
    zp = args.zip.resolve()
    if not zp.is_file():
        print(f"[cub-voc-zip] нет файла: {zp}", file=sys.stderr)
        return 2

    extracted = root / "raw" / "cub200_voc_extracted"
    marker = extracted / ".extracted_ok"
    need = args.force_extract or not marker.is_file()

    extracted.parent.mkdir(parents=True, exist_ok=True)
    if args.force_extract and extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True, exist_ok=True)

    if need or not _find_xml_root(extracted):
        print(f"[cub-voc-zip] распаковка {zp.name} → {extracted} …", flush=True)
        with zipfile.ZipFile(zp) as zf:
            zf.extractall(extracted)
        marker.write_text(str(zp.resolve()), encoding="utf-8")

    xml_inner = _find_xml_root(extracted)
    if xml_inner is None:
        print("[cub-voc-zip] после распаковки не найден train_images/train_labels рядом", file=sys.stderr)
        return 3

    _ensure_layout(root)
    tr, va, sk = _import_folder(xml_inner, root)
    print(
        f"[cub-voc-zip] из {xml_inner} → {root / 'binary' / 'birds'}: "
        f"train={tr} val={va} пропусков={sk}",
        flush=True,
    )
    if tr == 0 and va == 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
