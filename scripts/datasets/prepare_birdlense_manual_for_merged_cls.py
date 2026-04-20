#!/usr/bin/env python3
"""
Ручная выгрузка BirdLense → имена папок как в datasets/merged_cls (Latin (Common)).

Кропы в Hub часто лежат под «короткими» именами (Eurasian Jay, …) — здесь маппинг
на точные подкаталоги merged_cls.

Не включаем в merge-датасет:
  - Bird — бинарный класс детектора, не EU-классификатор;
  - Rodent — в merged_cls нет папки класса; грызуны остаются на детекторе.

Исключённые кропы копируются рядом в <output>_excluded/ (train|val/<как в источнике>/).

Пример:
  python scripts/datasets/prepare_birdlense_manual_for_merged_cls.py \\
    --input datasets/birdlense_dataset_20260420_1231Z \\
    --output datasets/birdlense_manual_for_merge
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Папка в ручной выгрузке → имя подкаталога в merged_cls (как в class_names.txt)
FOLDER_MAP: dict[str, str] = {
    "Corvus cornix (Hooded Crow)": "Corvus cornix (Hooded Crow)",
    "Eurasian Blue Tit": "Cyanistes caeruleus (Eurasian Blue Tit)",
    "Eurasian Jay": "Garrulus glandarius (Eurasian Jay)",
    "Eurasian Magpie": "Pica pica (Eurasian Magpie)",
    "Eurasian Nuthatch": "Sitta europaea (Eurasian Nuthatch)",
    "Great Tit": "Parus major (Great Tit)",
}

# Не для merged_cls (классификатор птиц)
EXCLUDED_RAW_NAMES = frozenset({"Bird", "Rodent"})


def _load_allowlist(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def _find_dataset_root(src: Path) -> Path:
    if (src / "train").is_dir():
        return src
    subs = [p for p in src.iterdir() if p.is_dir()]
    if len(subs) == 1 and (subs[0] / "train").is_dir():
        return subs[0]
    raise SystemExit(f"Не найден train/: ожидается {src}/train или {src}/<одна_подпапка>/train")


def _copy_split(
    src_root: Path,
    dst_root: Path,
    split: str,
    folder_map: dict[str, str],
    allowlist: set[str],
    excluded_root: Path,
) -> tuple[int, int]:
    """(число файлов в cls-merge датасете, число файлов в excluded)."""
    n_merged = 0
    n_excluded = 0
    split_src = src_root / split
    if not split_src.is_dir():
        return 0, 0
    split_dst = dst_root / split
    split_dst.mkdir(parents=True, exist_ok=True)

    for class_dir in sorted(split_src.iterdir()):
        if not class_dir.is_dir():
            continue
        raw_name = class_dir.name
        if raw_name in EXCLUDED_RAW_NAMES:
            dst_class = excluded_root / split / raw_name
            dst_class.mkdir(parents=True, exist_ok=True)
            for p in sorted(class_dir.iterdir()):
                if p.suffix.lower() not in IMAGE_EXTS:
                    continue
                shutil.copy2(p, dst_class / p.name)
                n_excluded += 1
            continue

        target = folder_map.get(raw_name)
        if not target:
            raise SystemExit(
                f"Неизвестная папка «{raw_name}» в {split_src}. "
                f"Добавьте строку в FOLDER_MAP в prepare_birdlense_manual_for_merged_cls.py."
            )
        if target not in allowlist:
            raise SystemExit(f"Класс «{target}» отсутствует в файле --class-names")
        out_dir = split_dst / target
        out_dir.mkdir(parents=True, exist_ok=True)
        for p in sorted(class_dir.iterdir()):
            if p.suffix.lower() not in IMAGE_EXTS:
                continue
            shutil.copy2(p, out_dir / p.name)
            n_merged += 1
    return n_merged, n_excluded


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Папка с train/ и val/ или каталог, куда распаковать ZIP",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/birdlense_manual_for_merge"),
        help="Готовый датасет для копирования в merged_cls",
    )
    ap.add_argument(
        "--class-names",
        type=Path,
        default=Path("app/processor/models/classification/weights/class_names.txt"),
    )
    ap.add_argument("--zip", type=Path, default=None, help="Распаковать этот ZIP в --input")
    args = ap.parse_args()

    if args.zip is not None:
        if not args.zip.is_file():
            raise SystemExit(f"ZIP не найден: {args.zip}")
        args.input.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.zip, "r") as zf:
            zf.extractall(args.input)
        if not (args.input / "train").is_dir():
            nested = args.input / args.zip.stem
            if nested.is_dir() and (nested / "train").is_dir():
                args.input = nested

    src_root = _find_dataset_root(args.input.resolve())
    dst_root = args.output.resolve()
    allowlist = _load_allowlist(args.class_names.resolve())

    excluded_root = dst_root.parent / f"{dst_root.name}_excluded"
    if dst_root.exists():
        shutil.rmtree(dst_root)
    if excluded_root.exists():
        shutil.rmtree(excluded_root)
    dst_root.mkdir(parents=True)

    total_merged = 0
    total_excluded = 0
    for split in ("train", "val"):
        nm, nx = _copy_split(
            src_root,
            dst_root,
            split,
            FOLDER_MAP,
            allowlist,
            excluded_root,
        )
        total_merged += nm
        total_excluded += nx

    train_root = dst_root / "train"
    classes_out = sorted(
        d.name for d in train_root.iterdir() if d.is_dir() and any(d.iterdir())
    )
    (dst_root / "classes.txt").write_text("\n".join(classes_out) + "\n", encoding="utf-8")

    (dst_root / "README_MERGE.txt").write_text(
        "Папки = имена в datasets/merged_cls/train|val (EU-классификатор).\n"
        "Слияние: rsync или копирование файлов в merged_cls/train/<класс>/ и val/<класс>/.\n"
        f"Bird и Rodent не входят в merged_cls: см. {excluded_root.name}/\n"
        "Rodent остаётся на бинарном детекторе; Bird — без вида в классификаторе.\n",
        encoding="utf-8",
    )

    print(f"Cls-merge: {dst_root} — {total_merged} изображений, {len(classes_out)} классов")
    if total_excluded:
        print(f"Исключено (Bird|Rodent): {total_excluded} файлов → {excluded_root}")


if __name__ == "__main__":
    main()
