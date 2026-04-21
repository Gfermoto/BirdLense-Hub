#!/usr/bin/env python3
r"""
Скопировать merged_cls в новый каталог и добавить кропы из addon (train/val).

Формат папок одинаковый: train|val/<Latin (Common)>/.
При коллизии имён файлов — суффикс _birdlenseN перед расширением.

  python merge_merged_cls_with_birdlense_addon.py \\
    --base datasets/merged_cls \\
    --addon datasets/birdlense_dataset_20260420 \\
    --output datasets/merged_cls_birdlense_20260420
"""  # noqa: E501

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}


def _unique_dst(class_dir: Path, name: str) -> Path:
    dst = class_dir / name
    if not dst.exists():
        return dst
    p = Path(name)
    stem, suf = p.stem, p.suffix
    n = 1
    while True:
        cand = class_dir / f'{stem}_birdlense{n}{suf}'
        if not cand.exists():
            return cand
        n += 1


def _copy_addon(base_out: Path, addon: Path) -> tuple[int, int]:
    """Возвращает (число скопированных файлов, пустых классов)."""
    n = 0
    skipped_classes = 0
    for split in ('train', 'val'):
        src_split = addon / split
        if not src_split.is_dir():
            continue
        for class_dir in sorted(src_split.iterdir()):
            if not class_dir.is_dir():
                continue
            dst_class = base_out / split / class_dir.name
            if not dst_class.is_dir():
                dst_class.mkdir(parents=True, exist_ok=True)
            files = [
                p for p in class_dir.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS
            ]
            if not files:
                skipped_classes += 1
                continue
            for p in sorted(files):
                dst = _unique_dst(dst_class, p.name)
                shutil.copy2(p, dst)
                n += 1
    return n, skipped_classes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--addon', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()

    base = args.base.resolve()
    addon = args.addon.resolve()
    out = args.output.resolve()

    if not (base / 'train').is_dir():
        raise SystemExit(f'Нет {base}/train')
    if not (addon / 'train').is_dir():
        raise SystemExit(f'Нет {addon}/train')

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(base, out, symlinks=False)

    copied, skip = _copy_addon(out, addon)
    print(f'База: {base}')
    print(
        f'Добавлено из {addon}: {copied} файлов '
        f'(пустых классов: {skip})',
    )
    print(f'Итог: {out}')


if __name__ == '__main__':
    main()
