#!/usr/bin/env python3
"""Импорт кадров «фон» из локальной папки в ``binary/background``.

Подходит для снимков с прод-камер BirdLense без объектов: в ``labels/*.txt``
пишутся **пустые** файлы (чистые негативы), как ожидает ``merge_datasets_three_class``.

Отбор «что подходит»:
- форматы: jpg/jpeg/png/webp;
- если есть пара ``photo_...@....jpg`` и ``photo_...@...._thumb.jpg`` (в т.ч. ``_thumb (1)``),
  берётся **полный** кадр;
- если есть только thumb — берётся он;
- при нескольких кандидатах на один логический stem — больший файл по байтам.

Пример::

    cd scripts/datasets
    python3 import_hub_background_folder.py \\
        --source detector/Background \\
        --prefix hubbg_

Дальше: ``merge_datasets_three_class`` / ``make dataset-merge-three-class`` или свой ``--output-dir brg``.
"""

from __future__ import annotations

import argparse
import random
import re
import shutil
import sys
from pathlib import Path

_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"}
_THUMB_SUFFIX = re.compile(r"_thumb(?: \(\d+\))?$", re.IGNORECASE)


def _normalize_stem(stem: str) -> str:
    return _THUMB_SUFFIX.sub("", stem)


def _is_thumb_name(name: str) -> bool:
    return "_thumb" in Path(name).stem.lower()


def _collect_best_per_key(src_dir: Path) -> list[Path]:
    by_key: dict[str, tuple[Path, bool, int]] = {}
    for p in sorted(src_dir.iterdir()):
        if not p.is_file() or p.suffix not in _IMG_EXT:
            continue
        if p.name.endswith(":Zone.Identifier") or "Zone.Identifier" in p.name:
            continue
        stem_norm = _normalize_stem(p.stem)
        thumb = _is_thumb_name(p.name)
        try:
            sz = p.stat().st_size
        except OSError:
            continue
        if sz < 512:
            continue
        prev = by_key.get(stem_norm)
        if prev is None:
            by_key[stem_norm] = (p, thumb, sz)
            continue
        prev_path, prev_thumb, prev_sz = prev
        if prev_thumb and not thumb:
            by_key[stem_norm] = (p, thumb, sz)
        elif thumb and not prev_thumb:
            pass
        elif sz > prev_sz:
            by_key[stem_norm] = (p, thumb, sz)
    return [t[0] for t in by_key.values()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Папка только с изображениями фона (плоская)",
    )
    ap.add_argument(
        "--datasets-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Каталог scripts/datasets (родитель binary/)",
    )
    ap.add_argument("--prefix", type=str, default="hubbg_", help="Префикс имён в binary/background")
    ap.add_argument("--val-ratio", type=float, default=0.15, help="Доля val (остальное train)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = args.source.resolve()
    if not src.is_dir():
        print(f"Not a directory: {src}", file=sys.stderr)
        return 2

    picked = _collect_best_per_key(src)
    if not picked:
        print("No suitable images found.", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    rng.shuffle(picked)
    n_val = max(1, int(round(len(picked) * args.val_ratio))) if len(picked) >= 2 else 0
    if len(picked) == 1:
        n_val = 0
    val_set = set(picked[:n_val]) if n_val else set()

    bg_root = args.datasets_root.resolve() / "binary" / "background"
    pref = args.prefix.strip() or "hubbg_"

    train_n = val_n = 0
    for p in picked:
        split = "val" if p in val_set else "train"
        stem = f"{pref}{_normalize_stem(p.stem)}"
        dst_img = bg_root / split / "images" / f"{stem}{p.suffix.lower()}"
        dst_lbl = bg_root / split / "labels" / f"{stem}.txt"
        if args.dry_run:
            if split == "val":
                val_n += 1
            else:
                train_n += 1
            continue
        dst_img.parent.mkdir(parents=True, exist_ok=True)
        dst_lbl.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst_img)
        dst_lbl.write_text("", encoding="utf-8")
        if split == "val":
            val_n += 1
        else:
            train_n += 1

    action = "Would place" if args.dry_run else "Placed"
    print(
        f"{action} {len(picked)} unique backgrounds "
        f"(train={train_n}, val={val_n}) from {src} → {bg_root} "
        f"(prefix={pref!r})",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
