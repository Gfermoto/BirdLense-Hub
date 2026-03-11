#!/usr/bin/env python3
"""
Объединение нескольких датасетов классификации в один.

Формат входа: каждый датасет — папка с train/ и/или val/,
внутри — подпапки по классам: train/Class_Name/img.jpg

Формат выхода: merged/train/Class_Name/, merged/val/Class_Name/
Стратифицированный split 80/20 если val отсутствует.

Использование:
    python merge_classification_datasets.py --inputs dataset1 dataset2 dataset3 --output merged
    # или через конфиг в скрипте
"""

import argparse
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

import numpy as np


def normalize_class_name(name: str) -> str:
    """Привести имя класса к формату папки: пробелы -> _, убрать спецсимволы."""
    s = str(name).strip()
    s = re.sub(r'[/\\:*?"<>|]', '_', s)
    s = s.replace(' ', '_').replace('-', '_')
    s = re.sub(r'_+', '_', s).strip('_')
    return s or 'unknown'


def collect_images_by_class(input_dirs: list[Path], split: str) -> dict[str, list[Path]]:
    """Собрать пути к изображениям по классам из нескольких датасетов."""
    by_class = defaultdict(list)
    for inp in input_dirs:
        split_dir = inp / split
        if not split_dir.exists():
            continue
        for class_dir in split_dir.iterdir():
            if not class_dir.is_dir():
                continue
            class_name = normalize_class_name(class_dir.name)
            for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp'):
                for p in class_dir.glob(ext):
                    by_class[class_name].append(p)
    return dict(by_class)


def main():
    parser = argparse.ArgumentParser(description='Merge classification datasets')
    parser.add_argument('--inputs', nargs='+', required=True,
                        help='Input dataset directories (each has train/ and optionally val/)')
    parser.add_argument('--output', default='merged_cls',
                        help='Output directory')
    parser.add_argument('--val-ratio', type=float, default=0.2,
                        help='Val split ratio if val/ missing (default 0.2)')
    parser.add_argument('--symlink', action='store_true',
                        help='Use symlinks instead of copy (saves disk, may fail on Windows)')
    args = parser.parse_args()

    input_dirs = [Path(p).resolve() for p in args.inputs]
    for d in input_dirs:
        if not d.exists():
            raise SystemExit(f'Input directory not found: {d}')

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    train_out = output / 'train'
    val_out = output / 'val'
    train_out.mkdir(exist_ok=True)
    val_out.mkdir(exist_ok=True)

    # Собрать все изображения по классам
    train_by_class = collect_images_by_class(input_dirs, 'train')
    val_by_class = collect_images_by_class(input_dirs, 'val')

    # Объединить классы из train и val
    all_classes = set(train_by_class) | set(val_by_class)
    if not all_classes:
        raise SystemExit('No images found in input directories')

    def do_copy(src, dst):
        src, dst = Path(src), Path(dst)
        if args.symlink:
            os.symlink(src.resolve(), dst)
        else:
            shutil.copy2(src, dst)
    total_train, total_val = 0, 0

    for class_name in sorted(all_classes):
        train_imgs = train_by_class.get(class_name, [])
        val_imgs = val_by_class.get(class_name, [])
        all_imgs = train_imgs + val_imgs

        if not all_imgs:
            continue

        (train_out / class_name).mkdir(exist_ok=True)
        (val_out / class_name).mkdir(exist_ok=True)

        # Если val пустой — сделать split
        if not val_imgs and len(all_imgs) >= 2:
            np.random.seed(42)
            idx = np.random.permutation(len(all_imgs))
            n_val = max(1, int(len(all_imgs) * args.val_ratio))
            val_idx = set(idx[:n_val])
            train_imgs = [all_imgs[i] for i in range(len(all_imgs)) if i not in val_idx]
            val_imgs = [all_imgs[i] for i in val_idx]

        used = set()
        for p in train_imgs:
            dst = train_out / class_name / p.name
            if p.name in used:
                dst = train_out / class_name / f"{p.stem}_{id(p)}{p.suffix}"
            used.add(dst.name)
            if not dst.exists():
                do_copy(p, dst)
            total_train += 1

        used_val = set()
        for p in val_imgs:
            dst = val_out / class_name / p.name
            if p.name in used_val:
                dst = val_out / class_name / f"{p.stem}_{id(p)}{p.suffix}"
            used_val.add(dst.name)
            if not dst.exists():
                do_copy(p, dst)
            total_val += 1

    print(f'Merged {len(all_classes)} classes: {total_train} train, {total_val} val')
    print(f'Output: {output}')


if __name__ == '__main__':
    main()
