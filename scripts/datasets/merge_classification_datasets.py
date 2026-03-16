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

# Канонический формат проекта = Common name (Eurasian Jay, Great Tit и т.д.)
# Загружаем маппинг variant -> canonical из app
def _load_canonical_mapping():
    try:
        import sys
        app_path = Path(__file__).resolve().parents[2] / 'app'
        if str(app_path) not in sys.path:
            sys.path.insert(0, str(app_path))
        from web.util import load_species_canonical_mapping
        return load_species_canonical_mapping()
    except Exception:
        return {}

_CANONICAL_MAPPING = _load_canonical_mapping()


def normalize_class_name(name: str, preserve_scientific_common: bool = True,
                         mapping: dict | None = None) -> str:
    """
    Привести имя класса к каноническому (Common name для проекта).
    mapping: variant -> canonical (напр. "Garrulus glandarius (Eurasian Jay)" -> "Eurasian Jay").
    Все варианты одного вида сливаются в одну папку.
    """
    s = str(name).strip()
    if not s:
        return 'unknown'
    # Нормализовать в canonical (Common name)
    if mapping and s in mapping:
        s = mapping[s]
    elif mapping:
        key = s.lower().replace('_', ' ')
        for k, v in mapping.items():
            if k.lower().replace('_', ' ') == key:
                s = v
                break
    s = re.sub(r'[/\\:*?"<>|]', '_', s)
    s = s.replace(' ', '_').replace('-', '_')
    s = re.sub(r'_+', '_', s).strip('_')
    return s or 'unknown'


def collect_images_by_class(input_dirs: list[Path], split: str,
                           mapping: dict | None = None) -> dict[str, list[Path]]:
    """Собрать пути к изображениям по классам из нескольких датасетов."""
    mapping = mapping or _INAT_MAPPING
    by_class = defaultdict(list)
    for inp in input_dirs:
        split_dir = inp / split
        if not split_dir.exists():
            continue
        for class_dir in split_dir.iterdir():
            if not class_dir.is_dir():
                continue
            class_name = normalize_class_name(class_dir.name, mapping=mapping)
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
    # Очистить выход — иначе остаются старые папки, YOLO падает (requires N classes)
    for d in (train_out, val_out):
        if d.exists():
            for sub in d.iterdir():
                if sub.is_dir():
                    shutil.rmtree(sub)
        d.mkdir(exist_ok=True)

    # Собрать все изображения по классам (нормализация в canonical = Common name)
    train_by_class = collect_images_by_class(input_dirs, 'train', mapping=_CANONICAL_MAPPING)
    val_by_class = collect_images_by_class(input_dirs, 'val', mapping=_CANONICAL_MAPPING)

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
    kept_classes = 0

    for class_name in sorted(all_classes):
        train_imgs = train_by_class.get(class_name, [])
        val_imgs = val_by_class.get(class_name, [])
        all_imgs = train_imgs + val_imgs

        if not all_imgs:
            continue

        # Если train или val пустой — сделать split (YOLO требует классы в обоих сплитах)
        if (not train_imgs or not val_imgs) and len(all_imgs) >= 2:
            np.random.seed(42)
            idx = np.random.permutation(len(all_imgs))
            n_val = max(1, int(len(all_imgs) * args.val_ratio))
            val_idx = set(idx[:n_val])
            train_imgs = [all_imgs[i] for i in range(len(all_imgs)) if i not in val_idx]
            val_imgs = [all_imgs[i] for i in val_idx]

        # Пропустить классы без изображений в обоих сплитах (YOLO не поддерживает)
        if not train_imgs or not val_imgs:
            continue

        kept_classes += 1
        (train_out / class_name).mkdir(exist_ok=True)
        (val_out / class_name).mkdir(exist_ok=True)

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

    skipped = len(all_classes) - kept_classes
    if skipped:
        print(f'Skipped {skipped} classes (no images in both train and val)')
    print(f'Merged {kept_classes} classes: {total_train} train, {total_val} val')
    print(f'Output: {output}')


if __name__ == '__main__':
    main()
