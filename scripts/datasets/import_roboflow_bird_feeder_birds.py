#!/usr/bin/env python3
"""Импорт Roboflow YOLO / YOLOv11 (Bird-Feeder и аналоги) в ``binary/birds`` или ``binary/rodent``
как один класс (id ``0`` в файлах; при merge три класса грызунам всё равно ставится Rodent).

В архиве несколько видов птиц (разные class id в ``*.txt``) — все строки переписываются
в класс ``0`` с сохранением bbox (YOLO normalized).

Roboflow кладёт сплит ``valid/`` или ``val/`` — в ``binary/<subdir>/val/`` (птицы или грызуны).
Опционально ``test/`` → ``binary/<subdir>/test/`` (чтобы ``merge_datasets_three_class`` видел test).

После ``zipfile.extractall`` часто появляется вложенная папка (имя проекта) —
скрипт сам ищет каталог, где лежит ``train/images``.

Имена файлов получают префикс (по умолчанию ``rfbf_``), чтобы не перезаписать кадры из COCO.

**Bird-Feeder (YOLOv11), версия датасета 3:** скачайте ZIP со страницы экспорта
https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11
(в браузере; при необходимости авторизация Roboflow). Лицензия — на карточке проекта (часто CC BY 4.0).

Пример::

    python3 import_roboflow_bird_feeder_birds.py \\
        --root ../../datasets/new/detector \\
        --zip ~/Downloads/bird-feeder-hhjks-3.yolov11.zip

Из корня репозитория::

    make dataset-import-roboflow-bird-feeder ROBOFLOW_ZIP=/path/to/export.zip

Скачать и импортировать через API (``ROBOFLOW_API_KEY``): ``download_roboflow_bird_feeder.py``
или ``make dataset-download-roboflow-bird-feeder``. Уже распакованное дерево:
``--extracted-dir /path/to/yolov11-export``.

Затем: ``make dataset-merge-three-class``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def find_roboflow_yolo_export_root(extracted: Path) -> Path:
    """Находит корень дерева ``train/images`` после распаковки ZIP."""
    if (extracted / "train" / "images").is_dir():
        return extracted
    if extracted.is_dir():
        for child in sorted(extracted.iterdir()):
            if child.is_dir() and (child / "train" / "images").is_dir():
                return child
    return extracted


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
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"):
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


def _download_zip(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "BirdLense-import/1"})
    with urlopen(req, timeout=600) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def run_import_from_extracted_base(
    extracted_base: Path,
    birds_root: Path,
    prefix: str,
    *,
    dry_run: bool,
    no_test: bool,
    allow_train_only: bool = False,
) -> int:
    """Импорт из уже распакованного дерева YOLO (корень или вложенная папка проекта)."""
    extracted = find_roboflow_yolo_export_root(extracted_base.resolve())

    mapping: list[tuple[str, str]] = [("train", "train")]

    val_rf = None
    if (extracted / "valid" / "images").is_dir():
        val_rf = "valid"
    elif (extracted / "val" / "images").is_dir():
        val_rf = "val"
    if val_rf is not None:
        mapping.append((val_rf, "val"))

    if not no_test and (extracted / "test" / "images").is_dir():
        mapping.append(("test", "test"))

    if len(mapping) == 1:
        if not (
            allow_train_only
            and mapping[0][0] == "train"
            and (extracted / "train" / "images").is_dir()
        ):
            print(
                "Не найдены сплиты valid/ или val/ с images/. "
                "Экспорт только train — добавьте --allow-train-only или включите val в Roboflow.",
                file=sys.stderr,
            )
            return 2

    total_copied = 0
    total_skip = 0
    for rf_split, out_split in mapping:
        c, s = _import_split(
            extracted,
            rf_split,
            out_split,
            birds_root,
            prefix,
            dry_run=dry_run,
        )
        print(f"[{rf_split} → {out_split}] copied={c} skipped={s}")
        total_copied += c
        total_skip += s

    action = "Would copy" if dry_run else "Copied"
    print(
        f"{action} {total_copied} images (single class id 0); skipped {total_skip}. "
        f"Destination: {birds_root}",
    )
    if not dry_run:
        print("Next: make dataset-merge-three-class")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--zip",
        type=Path,
        help="Локальный ZIP экспорта Roboflow YOLOv11",
    )
    src.add_argument(
        "--from-url",
        type=str,
        metavar="URL",
        help="Скачать ZIP по ссылке (если 403 — скачайте вручную и передайте --zip)",
    )
    src.add_argument(
        "--extracted-dir",
        type=Path,
        metavar="DIR",
        help="Уже распакованный YOLOv11 (train/images …); без ZIP",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "datasets" / "new" / "detector",
        help="Корень ETL (каталог с binary/birds или binary/rodent); как у convert_cub_to_yolo / bootstrap --root",
    )
    ap.add_argument(
        "--datasets-root",
        type=Path,
        default=None,
        help="Устарело: родитель каталога binary/ (например scripts/datasets). "
        "Если задан, переопределяет вывод вместо --root.",
    )
    ap.add_argument(
        "--binary-subdir",
        type=str,
        choices=("birds", "rodent"),
        default="birds",
        help="Подкаталог под --root: binary/birds (по умолчанию) или binary/rodent",
    )
    ap.add_argument(
        "--prefix",
        type=str,
        default="rfbf_",
        help="Префикс имён файлов в binary/<subdir>",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--allow-train-only",
        action="store_true",
        help="Экспорт Roboflow только train/ (нет val/valid) — не ошибка",
    )
    ap.add_argument(
        "--no-test",
        action="store_true",
        help="Не импортировать сплит test в binary/<subdir>/test",
    )
    args = ap.parse_args()

    sub = args.binary_subdir
    if args.datasets_root is not None:
        birds_root = args.datasets_root.resolve() / "binary" / sub
    else:
        birds_root = args.root.resolve() / "binary" / sub

    prefix = (args.prefix or "rfbf_").strip() or "rfbf_"

    if args.extracted_dir is not None:
        return run_import_from_extracted_base(
            args.extracted_dir,
            birds_root,
            prefix,
            dry_run=args.dry_run,
            no_test=args.no_test,
            allow_train_only=args.allow_train_only,
        )

    with tempfile.TemporaryDirectory(prefix="roboflow_bf_") as tmp:
        tmp_path = Path(tmp)
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir(parents=True)

        if args.from_url:
            zpath = tmp_path / "roboflow_export.zip"
            try:
                print(f"Downloading {args.from_url!r} …", flush=True)
                _download_zip(args.from_url, zpath)
            except URLError as e:
                print(f"Download failed: {e}", file=sys.stderr)
                return 2
        else:
            assert args.zip is not None
            zpath = args.zip.resolve()
            if not zpath.is_file():
                print(f"ZIP not found: {zpath}", file=sys.stderr)
                return 2

        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(extract_dir)

        return run_import_from_extracted_base(
            extract_dir,
            birds_root,
            prefix,
            dry_run=args.dry_run,
            no_test=args.no_test,
            allow_train_only=args.allow_train_only,
        )


if __name__ == "__main__":
    raise SystemExit(main())
