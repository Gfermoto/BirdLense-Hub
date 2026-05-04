#!/usr/bin/env python3
# flake8: noqa
"""
Пост-обработка YOLO classification layout (например datasets/new/classifier/yolo_cls).

1) Дедуп по хешу (первые max-hash-bytes файла, как в build_manifests): если один и тот же
   контент в train и val — удалить копию в val.
2) Ребаланс: если у класса опустел train или val — переразбить изображения класса (seed=42).
3) Нормализация имён папок к виду Scientific (Common) + канонический common из seed-мэппинга.
   Папки с одинаковым целевым именем сливаются.
4) Test: из val каждого класса переносится доля в test/ (не загубив минимум в val).
5) При --all: глобальный дедуп (один хеш — один файл во всём train/val/test) и снова ребаланс.

Пример:
  python3 scripts/datasets/refine_classifier_yolo_cls.py \\
    --root datasets/new/classifier/yolo_cls --all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT / "scripts" / "datasets") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "datasets"))

from species_format import (  # noqa: E402
    common_to_scientific_format,
    extract_common_for_lookup,
    format_scientific_common,
    load_inat_mapping,
    parse_scientific_common,
    to_folder_name,
)

_CANONICAL_MAP_PATH = REPO_ROOT / "app/web/seed/species_canonical_mapping.txt"


def _norm_canon_key(name: str) -> str:
    s = str(name or "").strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def load_species_canonical_mapping_standalone() -> dict[str, str]:
    """Только seed-файл, без Flask/SQLAlchemy."""
    result: dict[str, str] = {}
    if not _CANONICAL_MAP_PATH.is_file():
        return result
    for line in _CANONICAL_MAP_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        variant, canonical = line.split("|", 1)
        canonical_name = canonical.strip()
        variant_name = variant.strip()
        result[variant_name] = canonical_name
        result[_norm_canon_key(variant_name)] = canonical_name
    return result


def normalize_species_to_canonical_standalone(name: str, mapping: dict[str, str]) -> str:
    direct = mapping.get(name)
    if direct:
        return direct
    norm_key = _norm_canon_key(name)
    by_norm = {_norm_canon_key(k): v for k, v in mapping.items() if str(k or "").strip()}
    return by_norm.get(norm_key, name)


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _hash_file(path: Path, max_bytes: int) -> str:
    h = hashlib.sha256()
    remaining = max(0, int(max_bytes))
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024 if remaining <= 0 else min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            if remaining > 0:
                remaining -= len(chunk)
                if remaining <= 0:
                    break
    return h.hexdigest()


def _iter_class_images(split_dir: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    if not split_dir.is_dir():
        return out
    for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        for ext in IMAGE_EXTS:
            for p in class_dir.glob(f"*{ext}"):
                out.append((class_dir.name, p))
    return out


def _unlink_if_exists(p: Path) -> None:
    if p.is_symlink() or p.is_file():
        p.unlink()


def dedupe_cross_split(root: Path, max_hash_bytes: int) -> dict[str, int]:
    """Удалить из val файлы, чей хеш уже есть в train (тот же класс)."""
    removed = 0
    checked = 0
    train_root = root / "train"
    val_root = root / "val"
    if not train_root.is_dir() or not val_root.is_dir():
        return {"removed_val_dupes": 0, "skipped": 0}

    train_hashes: dict[tuple[str, str], str] = {}
    for cls, path in _iter_class_images(train_root):
        h = _hash_file(path, max_hash_bytes)
        train_hashes[(cls, h)] = str(path)

    for cls, path in _iter_class_images(val_root):
        checked += 1
        h = _hash_file(path, max_hash_bytes)
        key = (cls, h)
        if key in train_hashes:
            _unlink_if_exists(path)
            removed += 1
    return {"removed_val_dupes": removed, "val_files_checked": checked}


def cleanup_empty_class_dirs(root: Path) -> int:
    removed = 0
    for split in ("train", "val", "test"):
        sp = root / split
        if not sp.is_dir():
            continue
        for class_dir in sorted(sp.iterdir(), key=lambda p: p.name):
            if not class_dir.is_dir():
                continue
            if any(class_dir.iterdir()):
                continue
            class_dir.rmdir()
            removed += 1
    return removed


def dedupe_global_across_splits(root: Path, max_hash_bytes: int) -> dict[str, int]:
    """
    Один хеш — только один файл во всём дереве train/val/test.
    Оставляем экземпляр в приоритете: train → val → test.
    """
    priority = {"train": 0, "val": 1, "test": 2}
    by_hash: dict[str, list[tuple[str, str, Path]]] = defaultdict(list)
    for split in ("train", "val", "test"):
        sp = root / split
        if not sp.is_dir():
            continue
        for cls, path in _iter_class_images(sp):
            by_hash[_hash_file(path, max_hash_bytes)].append((split, cls, path))
    removed = 0
    for lst in by_hash.values():
        if len(lst) <= 1:
            continue
        lst.sort(key=lambda t: priority[t[0]])
        for _split, _cls, path in lst[1:]:
            _unlink_if_exists(path)
            removed += 1
    emptied = cleanup_empty_class_dirs(root)
    return {"removed_global_dupes": removed, "empty_class_dirs_removed": emptied}


def _collect_by_class(split_dir: Path) -> dict[str, list[Path]]:
    by_c: dict[str, list[Path]] = {}
    for cls, path in _iter_class_images(split_dir):
        by_c.setdefault(cls, []).append(path)
    return by_c


def rebalance_splits(root: Path, val_ratio: float, seed: int = 42) -> dict[str, int]:
    """
    Для каждого класса обеспечить непустые train и val (если суммарно >= 2 файлов).
    Все файлы класса собираются, перемешиваются, режутся по val_ratio в val.
    """
    rng = np.random.default_rng(seed)
    moved = 0
    train_root = root / "train"
    val_root = root / "val"
    all_classes = set(_collect_by_class(train_root)) | set(_collect_by_class(val_root))

    for cls in sorted(all_classes):
        tr = train_root / cls
        va = val_root / cls
        paths: list[Path] = []
        if tr.is_dir():
            paths.extend([p for p in tr.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
        if va.is_dir():
            paths.extend([p for p in va.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
        if len(paths) < 2:
            continue
        rng.shuffle(paths)
        n_val = max(1, int(round(len(paths) * val_ratio)))
        n_val = min(n_val, len(paths) - 1)
        val_set = set(paths[:n_val])
        tr.mkdir(parents=True, exist_ok=True)
        va.mkdir(parents=True, exist_ok=True)
        for p in paths:
            target_dir = va if p in val_set else tr
            dest = target_dir / p.name
            if p.resolve() == dest.resolve():
                continue
            if dest.exists() and dest != p:
                dest = target_dir / f"{p.stem}_{hash(p) & 0xFFFF:x}{p.suffix}"
            shutil.move(str(p), str(dest))
            moved += 1
        for d in (tr, va):
            if d.is_dir() and not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:
                    pass
    return {"rebalance_moves": moved}


def _folder_to_label(folder: str, inat_map: dict[str, str]) -> str:
    """Имя папки -> строка Scientific (Common) или common."""
    m = re.match(r"^(.+)_\((.+)\)$", folder)
    if m:
        sci = m.group(1).replace("_", " ").strip()
        com = m.group(2).replace("_", " ").strip()
        return format_scientific_common(sci, com)
    raw = folder.replace("_", " ")
    got = common_to_scientific_format(raw, inat_map)
    if got != raw:
        return got
    return raw.strip()


def _label_to_target_folder(label: str, canon_map: dict) -> str:
    common_key = extract_common_for_lookup(label)
    canon = normalize_species_to_canonical_standalone(common_key, canon_map)
    sci, _com_parsed = parse_scientific_common(label)
    if sci and canon:
        full = format_scientific_common(sci, canon)
    elif canon:
        full = canon
    else:
        full = label
    return to_folder_name(full)


def normalize_class_names(root: Path, cache_dir: Path) -> dict[str, int]:
    """
    Переименовать папки классов к каноническому виду (имена папок = to_folder_name(...)).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    inat_map = load_inat_mapping(cache_dir)
    canon_map = load_species_canonical_mapping_standalone()

    mapping: dict[str, str] = {}
    for split in ("train", "val", "test"):
        sp = root / split
        if not sp.is_dir():
            continue
        for class_dir in sorted(p for p in sp.iterdir() if p.is_dir()):
            label = _folder_to_label(class_dir.name, inat_map)
            target = _label_to_target_folder(label, canon_map)
            if not target or target == "unknown":
                target = to_folder_name(label)
            mapping[class_dir.name] = target

    merged_dirs = 0
    moves = 0
    for split in ("train", "val", "test"):
        sp = root / split
        if not sp.is_dir():
            continue
        buckets: dict[str, list[Path]] = {}
        for class_dir in sorted(p for p in sp.iterdir() if p.is_dir()):
            tgt = mapping.get(class_dir.name, class_dir.name)
            buckets.setdefault(tgt, []).append(class_dir)

        for tgt_name, dirs in buckets.items():
            final_dir = sp / tgt_name
            final_dir.mkdir(parents=True, exist_ok=True)
            if len(dirs) == 1 and dirs[0].name == tgt_name:
                continue
            for d in dirs:
                if d.resolve() == final_dir.resolve():
                    continue
                for p in list(d.iterdir()):
                    if not p.is_file():
                        continue
                    dest = final_dir / p.name
                    if dest.exists():
                        dest = final_dir / f"{p.stem}_{hash(p) & 0xFFFFFFFF:x}{p.suffix}"
                    shutil.move(str(p), str(dest))
                    moves += 1
                try:
                    remaining = list(d.iterdir())
                    if not remaining:
                        d.rmdir()
                except OSError:
                    pass
            merged_dirs += max(0, len(dirs) - 1)
    return {"normalize_moves": moves, "merged_source_dirs": merged_dirs}


def carve_test_split(root: Path, test_ratio: float, seed: int = 43) -> dict[str, int]:
    """Перенести часть val -> test, оставив в val хотя бы один файл (если возможно)."""
    rng = np.random.default_rng(seed)
    val_root = root / "val"
    test_root = root / "test"
    test_root.mkdir(parents=True, exist_ok=True)
    moved = 0
    if not val_root.is_dir():
        return {"test_moves": 0}

    for class_dir in sorted(p for p in val_root.iterdir() if p.is_dir()):
        imgs = sorted(
            p for p in class_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        )
        if len(imgs) < 2:
            continue
        rng.shuffle(imgs)
        n_test = max(1, int(round(len(imgs) * test_ratio)))
        n_test = min(n_test, len(imgs) - 1)
        if n_test <= 0:
            continue
        take = imgs[:n_test]
        td = test_root / class_dir.name
        td.mkdir(parents=True, exist_ok=True)
        for p in take:
            dest = td / p.name
            if dest.exists():
                dest = td / f"{p.stem}_{hash(p) & 0xFFFF:x}{p.suffix}"
            shutil.move(str(p), str(dest))
            moved += 1
        if class_dir.is_dir() and not any(class_dir.iterdir()):
            class_dir.rmdir()
    return {"test_moves": moved}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="Путь к yolo_cls (train/val[/test])")
    ap.add_argument("--cache-dir", type=Path, default=REPO_ROOT / "datasets/new/classifier/.cache")
    ap.add_argument("--max-hash-bytes", type=int, default=1024 * 1024)
    ap.add_argument("--val-ratio", type=float, default=0.2, help="При ребалансе")
    ap.add_argument("--test-ratio", type=float, default=0.1, help="Доля val -> test")
    ap.add_argument("--dedupe", action="store_true")
    ap.add_argument("--rebalance", action="store_true")
    ap.add_argument("--normalize", action="store_true")
    ap.add_argument("--test-split", action="store_true", dest="do_test")
    ap.add_argument("--all", action="store_true", help="Все шаги в безопасном порядке")
    ap.add_argument(
        "--dedupe-global-only",
        action="store_true",
        help="Глобальный дедуп train/val/test, ребаланс train/val, очистка пустых папок",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"root not found: {root}")

    stats: dict[str, object] = {"root": str(root)}
    steps = []
    if args.dedupe_global_only:
        stats.update(dedupe_global_across_splits(root, args.max_hash_bytes))
        stats.update(rebalance_splits(root, args.val_ratio))
        stats["empty_class_dirs_removed_after_rebalance"] = cleanup_empty_class_dirs(root)
        print(json.dumps({"ok": True, **stats}, ensure_ascii=False, indent=2))
        return 0

    if args.all:
        args.dedupe = args.rebalance = args.normalize = args.do_test = True

    if args.dedupe:
        steps.append(dedupe_cross_split(root, args.max_hash_bytes))
    if args.rebalance:
        steps.append(rebalance_splits(root, args.val_ratio))
    if args.normalize:
        steps.append(normalize_class_names(root, args.cache_dir.resolve()))
        steps.append(rebalance_splits(root, args.val_ratio))
    if args.do_test:
        steps.append(carve_test_split(root, args.test_ratio))

    if args.all:
        steps.append(dedupe_global_across_splits(root, args.max_hash_bytes))
        steps.append(rebalance_splits(root, args.val_ratio))

    for s in steps:
        stats.update(s)

    print(json.dumps({"ok": True, **stats}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
