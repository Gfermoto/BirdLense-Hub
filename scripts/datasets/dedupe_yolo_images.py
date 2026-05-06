#!/usr/bin/env python3
"""Удалить дубликаты изображений в YOLO-датасете (train|val|test)/images по SHA256.

Дубликаты вида ``b_000000000143.jpg`` и ``b_000000000143_1.jpg`` (старый bootstrap с суффиксами;
в актуальном bootstrap такие кадры пропускаются — см. ``_copy_once``).
имеют одинаковые байты — остаётся один файл; соответствующие ``labels/*.txt`` синхронно.

Опционально ``--drop-val-if-in-train``: если тот же хеш есть в train, копии в val удаляются
(снижает утечку train→val).

После ``merge_datasets_three_class`` (префиксы ``b_``, ``r_``, ``g_``) один и тот же JPEG может
лежать под разными именами; либо дубли суффиксов ``_*``. Используйте ``--detector-merge`` для
одного прохода по всем сплитам: один SHA256 → один файл. По умолчанию ``--detector-merge-strategy
source-aware``: класс **Bird > Rodent > Background**, затем **источник** по имени файла
(COCO и OID hex важнее CUB и Roboflow rfbf), затем сплит **train > val > test**,
имя без суффикса ``_123``. Старое поведение:
``--detector-merge-strategy class-first``.

Пример::

    python3 dedupe_yolo_images.py --root brg
    python3 dedupe_yolo_images.py --root brg --dry-run
    python3 dedupe_yolo_images.py --root datasets/new/detector/yolo --detector-merge
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"}
_STEM_NUM_SUFFIX = re.compile(r"_\d+$")

# merge_datasets_three_class.py: b_=bird, r_=rodent, g_=background (legacy «g» = ground)
_DETECTOR_PREFIX_RANK = {"b_": 0, "r_": 1, "g_": 2}
_SPLIT_RANK = {"train": 0, "val": 1, "test": 2}

# При коллизии одних и тех же байт в разных файлах merged-датасета (после merge_datasets_three_class):
# сначала класс b_ > r_ > g_, затем для птиц/фона — предпочесть «полевые» источники (COCO, OID), не fine-grained CUB.
# Меньше число = выше приоритет оставить файл.
_SOURCE_TIER_COCO_12 = 0
_SOURCE_TIER_OID_HEX = 1
_SOURCE_TIER_ROBOFLOW = 2
_SOURCE_TIER_CUB = 3
_SOURCE_TIER_HUBBG = 4
_SOURCE_TIER_UNKNOWN = 9


def _merged_body_after_prefix(filename: str) -> str:
    """Имя без префикса ``b_`` / ``r_`` / ``g_``."""
    for pref in ("b_", "r_", "g_"):
        if filename.startswith(pref):
            return filename[len(pref) :]
    return filename


def _source_tier_merged_body(body: str) -> int:
    """Приоритет источника по имени файла после префикса merge (для одного класса/prefix)."""
    b = body
    bl = b.lower()
    if bl.startswith("hubbg_"):
        return _SOURCE_TIER_HUBBG
    if bl.startswith("rfbf_"):
        return _SOURCE_TIER_ROBOFLOW
    if bl.startswith("cub_"):
        return _SOURCE_TIER_CUB
    if re.match(r"^[0-9]{12}\.jpe?g$", b, re.I):
        return _SOURCE_TIER_COCO_12
    if re.match(r"^[0-9a-f]{16}\.jpe?g$", b, re.I):
        return _SOURCE_TIER_OID_HEX
    return _SOURCE_TIER_UNKNOWN


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _keeper_score(path: Path, *, detector_merge: bool = False) -> tuple:
    """Меньше = лучше: без суффикса ``_123`` у stem предпочтительнее.

    С ``detector_merge``: префикс ``b_`` / ``r_`` / ``g_`` (приоритет bird > rodent > bg).
    """
    stem = path.stem
    penal = 1 if _STEM_NUM_SUFFIX.search(stem) else 0
    name = path.name
    if not detector_merge:
        return (penal, stem, name)
    pr = 9
    for pref, r in _DETECTOR_PREFIX_RANK.items():
        if name.startswith(pref):
            pr = r
            break
    return (pr, penal, stem, name)


def _label_path(img: Path) -> Path:
    return img.parent.parent / "labels" / f"{img.stem}.txt"


def _dedupe_split(
    images_dir: Path,
    dataset_root: Path,
    *,
    dry_run: bool,
    detector_merge: bool = False,
) -> dict:
    """Внутри одного сплита: один хеш → один файл."""
    removed: list[str] = []
    kept_groups = 0
    if not images_dir.is_dir():
        return {"removed": removed, "duplicate_groups": 0}

    by_hash: dict[str, list[Path]] = defaultdict(list)
    for p in sorted(images_dir.iterdir()):
        if not p.is_file() or p.suffix not in _IMG_EXT:
            continue
        by_hash[_sha256(p)].append(p)

    def _key(pp: Path) -> tuple:
        return _keeper_score(pp, detector_merge=detector_merge)

    for digest, paths in by_hash.items():
        if len(paths) <= 1:
            continue
        kept_groups += 1
        keeper = min(paths, key=_key)
        for p in paths:
            if p == keeper:
                continue
            lbl = _label_path(p)
            removed.append(str(p.relative_to(dataset_root)))
            if not dry_run:
                p.unlink(missing_ok=True)
                lbl.unlink(missing_ok=True)

    return {"removed": removed, "duplicate_groups": kept_groups}


def _glob_key_detector_class_first(split: str, path: Path) -> tuple:
    """Старый ключ: только класс b_/r_/g_, затем сплит (CUB мог «вытеснять» COCO при одинаковых байтах)."""
    stem = path.stem
    penal = 1 if _STEM_NUM_SUFFIX.search(stem) else 0
    name = path.name
    pr = 9
    for pref, r in _DETECTOR_PREFIX_RANK.items():
        if name.startswith(pref):
            pr = r
            break
    sr = _SPLIT_RANK.get(split, 9)
    return (pr, sr, penal, stem, name)


def _glob_key_detector_source_aware(split: str, path: Path) -> tuple:
    """Класс → источник (COCO/OID выше CUB/rfbf для детекции) → сплит → суффикс _123."""
    stem = path.stem
    penal = 1 if _STEM_NUM_SUFFIX.search(stem) else 0
    name = path.name
    pr = 9
    for pref, r in _DETECTOR_PREFIX_RANK.items():
        if name.startswith(pref):
            pr = r
            break
    body = _merged_body_after_prefix(name)
    st = _source_tier_merged_body(body)
    sr = _SPLIT_RANK.get(split, 9)
    return (pr, st, sr, penal, stem, name)


def _merge_class_prefix(filename: str) -> str:
    """Классовый префикс merged-датасета: ``b_`` / ``r_`` / ``g_`` или ``_`` если без префикса."""
    for pref in ("b_", "r_", "g_"):
        if filename.startswith(pref):
            return pref
    return "_"


def _dedupe_detector_merge_global(
    dataset_root: Path,
    *,
    dry_run: bool,
    merge_strategy: str = "source-aware",
    merge_scope: str = "within-prefix",
) -> dict:
    """Дубликаты по SHA256. По умолчанию ``within-prefix``: только внутри одного класса (b_/r_/g_),
    одинаковые байты в птице и фоне **не сливаются**. Режим ``global`` удаляет между классами —
    опасен, оставлен только для осознанной очистки.
    """
    items: list[tuple[str, Path]] = []
    for sp in ("train", "val", "test"):
        img_dir = dataset_root / sp / "images"
        if not img_dir.is_dir():
            continue
        for p in sorted(img_dir.iterdir()):
            if p.is_file() and p.suffix in _IMG_EXT:
                items.append((sp, p))

    by_key: dict[tuple[str, str], list[tuple[str, Path]]] = defaultdict(list)
    for sp, p in items:
        digest = _sha256(p)
        if merge_scope == "within-prefix":
            bucket = _merge_class_prefix(p.name)
            key = (digest, bucket)
        elif merge_scope == "global":
            key = (digest, "*")
        else:
            raise ValueError(f"unknown merge_scope: {merge_scope!r}")
        by_key[key].append((sp, p))

    removed: list[str] = []
    kept_groups = 0

    key_fn = _glob_key_detector_source_aware
    if merge_strategy == "class-first":
        key_fn = _glob_key_detector_class_first
    elif merge_strategy != "source-aware":
        raise ValueError(f"unknown merge_strategy: {merge_strategy!r}")

    for _key_tuple, lst in by_key.items():
        if len(lst) <= 1:
            continue
        kept_groups += 1
        _keeper_sp, keeper_p = min(lst, key=lambda t: key_fn(t[0], t[1]))
        for sp, p in lst:
            if p.resolve() == keeper_p.resolve():
                continue
            removed.append(str(Path(sp) / "images" / p.name))
            if not dry_run:
                lbl = _label_path(p)
                p.unlink(missing_ok=True)
                lbl.unlink(missing_ok=True)

    return {
        "removed": removed,
        "duplicate_groups": kept_groups,
        "merge_scope": merge_scope,
        "merge_strategy": merge_strategy,
    }


def _cross_split_drop_val(
    root: Path,
    splits: list[str],
    *,
    dry_run: bool,
) -> list[str]:
    """Удалить из val (и др.) изображения, если тот же хеш уже есть в train."""
    hash_to_train: dict[str, Path] = {}
    train_img = root / "train" / "images"
    if train_img.is_dir():
        for p in train_img.iterdir():
            if p.is_file() and p.suffix in _IMG_EXT:
                hash_to_train.setdefault(_sha256(p), p)

    removed: list[str] = []
    for sp in splits:
        if sp == "train":
            continue
        img_dir = root / sp / "images"
        if not img_dir.is_dir():
            continue
        for p in sorted(img_dir.iterdir()):
            if not p.is_file() or p.suffix not in _IMG_EXT:
                continue
            d = _sha256(p)
            if d in hash_to_train:
                tr = hash_to_train[d]
                if p.resolve() == tr.resolve():
                    continue
                removed.append(f"{sp}:{p.name} (same as train/{tr.name})")
                if not dry_run:
                    lbl = _label_path(p)
                    p.unlink(missing_ok=True)
                    lbl.unlink(missing_ok=True)
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path("brg"),
        help="Корень датасета (train|val/images)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Только отчёт, файлы не трогать",
    )
    ap.add_argument(
        "--no-drop-val-if-in-train",
        action="store_false",
        dest="drop_val_if_in_train",
        default=True,
        help="Не удалять val/test, если тот же SHA256 уже есть в train (по умолчанию удаляем)",
    )
    ap.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Куда записать JSON-отчёт (по умолчанию: <root>/dedupe_report.json)",
    )
    ap.add_argument(
        "--detector-merge",
        action="store_true",
        help="Режим merged детектора (префиксы b_/r_/g_). По умолчанию дедуп только внутри класса.",
    )
    ap.add_argument(
        "--detector-merge-scope",
        choices=("within-prefix", "global"),
        default="within-prefix",
        help="within-prefix (по умолчанию): один SHA256 только среди b_* или только среди r_* или только g_* — "
        "не удалять птицу из-за совпадения с фоном. global: один хеш на весь датасет — может снести тысячи файлов.",
    )
    ap.add_argument(
        "--detector-merge-strategy",
        choices=("source-aware", "class-first"),
        default="source-aware",
        help="При конфликте внутри класса: source-aware — COCO/OID выше CUB/rfbf; class-first — старый порядок.",
    )
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    splits = []
    for sp in ("train", "val", "test"):
        if (root / sp / "images").is_dir():
            splits.append(sp)

    report: dict = {"root": str(root), "dry_run": args.dry_run, "per_split": {}, "cross_split_removed": []}

    total_removed = 0
    if args.detector_merge:
        if args.detector_merge_scope == "global":
            print(
                "[detector-merge] ВНИМАНИЕ: scope=global удаляет дубликаты между b_/r_/g_ — "
                "используйте только осознанно.",
                file=sys.stderr,
                flush=True,
            )
        sub_g = _dedupe_detector_merge_global(
            root,
            dry_run=args.dry_run,
            merge_strategy=args.detector_merge_strategy,
            merge_scope=args.detector_merge_scope,
        )
        report["detector_merge_global"] = sub_g
        total_removed += len(sub_g["removed"])
        print(
            f"[detector-merge scope={sub_g.get('merge_scope', '?')}] "
            f"duplicate groups: {sub_g['duplicate_groups']}, "
            f"files removed: {len(sub_g['removed'])}"
        )
    else:
        for sp in splits:
            sub = _dedupe_split(root / sp / "images", root, dry_run=args.dry_run, detector_merge=False)
            report["per_split"][sp] = sub
            n = len(sub["removed"])
            total_removed += n
            print(f"[{sp}] duplicate groups merged: {sub['duplicate_groups']}, files removed: {n}")

        if args.drop_val_if_in_train:
            xr = _cross_split_drop_val(root, splits, dry_run=args.dry_run)
            report["cross_split_removed"] = xr
            total_removed += len(xr)
            print(f"[cross-split] removed (val/test same bytes as train): {len(xr)}")

    out_report = args.report or (root / "dedupe_report.json")
    if not args.dry_run or args.report:
        out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Report -> {out_report}")

    print(f"Total files removed: {total_removed}" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
