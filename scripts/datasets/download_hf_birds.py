#!/usr/bin/env python3
"""
Скачать датасет с Hugging Face и конвертировать в формат YOLO classification.

Поддерживаемые датасеты:
  - 34data/birds-525-species
  - sasha/birdsnap (нужен bbox для crop)

Формат выхода: output_dir/train/Class_Name/img.jpg, output_dir/val/Class_Name/

Использование:
    pip install datasets huggingface_hub
    python download_hf_birds.py --dataset 34data/birds-525-species --output birds_525_cls
"""  # noqa: E501

import argparse
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    raise SystemExit('pip install datasets')

from tqdm import tqdm


def normalize_class_name(name: str) -> str:
    """Привести имя класса к формату папки."""
    import re
    s = str(name).strip()
    s = re.sub(r'[/\\:*?"<>|]', '_', s)
    s = s.replace(' ', '_').replace('-', '_')
    s = re.sub(r'_+', '_', s).strip('_')
    return s or 'unknown'


def download_birds_525(repo_id: str, output_dir: Path, val_ratio: float = 0.2):
    """34data/birds-525-species: image + labels."""
    ds = load_dataset(repo_id, split='train')
    cols = ds.column_names

    # Ищем колонки: image, label/labels
    img_col = 'image' if 'image' in cols else 'img'
    if img_col not in cols:
        img_col = next((c for c in cols if 'image' in c.lower()), None)
    if not img_col:
        raise SystemExit(f'No image column found. Columns: {cols}')

    label_col = None
    for c in ('labels', 'label', 'species', 'class', 'class_name'):
        if c in cols:
            label_col = c
            break
    if not label_col:
        # Может быть числовой id — нужен маппинг
        for c in cols:
            if c != img_col and 'image' not in c.lower():
                label_col = c
                break
    if not label_col:
        raise SystemExit(f'No label column found. Columns: {cols}')

    # Получить имена классов
    if 'labels' in ds.features:
        features = ds.features['labels']
        if hasattr(features, 'names'):
            id_to_name = dict(enumerate(features.names))
        else:
            id_to_name = {}
    else:
        id_to_name = {}

    (output_dir / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'val').mkdir(parents=True, exist_ok=True)

    n_val = int(len(ds) * val_ratio) if val_ratio > 0 else 0
    indices = list(range(len(ds)))
    if n_val > 0:
        import random
        random.seed(42)
        random.shuffle(indices)
        val_idx = set(indices[:n_val])
    else:
        val_idx = set()

    # 34data/birds-525: filename = "SPECIES NAME/001.jpg" → извлечь вид
    def get_class_name(label):
        if isinstance(label, int):
            return id_to_name.get(label, str(label))
        s = str(label)
        if '/' in s and not s.startswith('/'):
            s = s.split('/')[0]  # "GOLDEN BOWER BIRD/001.jpg" → "GOLDEN BOWER BIRD"
        return s

    for i in tqdm(indices, desc='Saving'):
        row = ds[i]
        img = row[img_col]
        label = row[label_col]
        class_name = normalize_class_name(get_class_name(label))

        split = 'val' if i in val_idx else 'train'
        out_dir = output_dir / split / class_name
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{i:06d}.jpg"
        out_path = out_dir / fname
        try:
            if hasattr(img, 'save'):
                img.save(out_path)
            else:
                from PIL import Image
                import io
                if isinstance(img, Image.Image):
                    img.save(out_path)
                elif isinstance(img, bytes):
                    Image.open(io.BytesIO(img)).convert('RGB').save(out_path)
                else:
                    raise ValueError('Unknown image type: ' + str(type(img)))
        except Exception as e:
            # Пропустить повреждённые/неподдерживаемые изображения
            if i < 3:  # Логировать только первые
                print(f'Skip {i}: {e}')
            continue

    print(f'Saved to {output_dir}')


def download_birdsnap(repo_id: str, output_dir: Path, val_ratio: float = 0.05):
    """sasha/birdsnap: bbox + species_id, crop по bbox."""
    import numpy as np
    from PIL import Image
    ds = load_dataset(repo_id, split='train')
    cols = ds.column_names

    # Birdsnap: bb_x1, bb_y1, bb_x2, bb_y2, species_id
    has_bbox = 'bb_x1' in cols or 'bb_x2' in cols
    if not has_bbox:
        raise SystemExit(
            'Birdsnap: bbox columns not found. Structure may have changed.'
        )

    (output_dir / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'val').mkdir(parents=True, exist_ok=True)

    # Словарь species_id -> name (нужен species.txt или из features)
    species_names = {}
    if 'species_id' in ds.features:
        # Может быть ClassLabel
        pass
    # Пока используем species_id как имя

    n_val = int(len(ds) * val_ratio) if val_ratio > 0 else 0
    indices = list(range(len(ds)))
    if n_val > 0:
        import random
        random.seed(42)
        random.shuffle(indices)
        val_idx = set(indices[:n_val])
    else:
        val_idx = set()

    for i in tqdm(indices, desc='Birdsnap'):
        row = ds[i]
        img = row.get('image') or row.get('img')
        if img is None:
            continue
        x1 = int(row.get('bb_x1', 0))
        y1 = int(row.get('bb_y1', 0))
        x2 = int(row.get('bb_x2', 0))
        y2 = int(row.get('bb_y2', 0))
        species_id = row.get('species_id', 0)
        class_name = species_names.get(species_id, f'species_{species_id}')
        class_name = normalize_class_name(class_name)

        # Crop
        if hasattr(img, 'save'):
            arr = np.array(img)
        else:
            arr = img
        if arr is not None and x2 > x1 and y2 > y1:
            h, w = arr.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            pad = 0.1
            pw = int((x2 - x1) * pad)
            ph = int((y2 - y1) * pad)
            x1, y1 = max(0, x1 - pw), max(0, y1 - ph)
            x2, y2 = min(w, x2 + pw), min(h, y2 + ph)
            crop = arr[y1:y2, x1:x2]
            if crop.size > 0:
                img = Image.fromarray(crop)

        split = 'val' if i in val_idx else 'train'
        out_dir = output_dir / split / class_name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{i:06d}.jpg"
        if hasattr(img, 'save'):
            img.save(out_path)
        elif arr is not None:
            Image.fromarray(arr).save(out_path)

    print(f'Saved to {output_dir}')


def main():
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default='34data/birds-525-species',
                        help='Hugging Face dataset ID')
    parser.add_argument('--output', default='birds_hf_cls',
                        help='Output directory')
    parser.add_argument('--val-ratio', type=float, default=0.2)
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    if 'birdsnap' in args.dataset.lower():
        download_birdsnap(args.dataset, output, args.val_ratio)
    else:
        download_birds_525(args.dataset, output, args.val_ratio)


if __name__ == '__main__':
    main()
