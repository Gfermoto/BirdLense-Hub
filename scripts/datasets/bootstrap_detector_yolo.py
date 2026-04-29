#!/usr/bin/env python3
"""
Заполняет дерево ``binary/`` под ``merge_datasets_three_class.py``:

  binary/birds/      — COCO 2017, только класс ``bird`` → один класс в YOLO (id 0).
  binary/rodent/     — Open Images V6, ``Squirrel`` → один класс (id 0); после merge → Rodent.
  binary/background/ — COCO train/val: кадры **без** ``bird``, пустые ``.txt``.

Зависимости::

    pip install fiftyone pyyaml

Первый запуск качает выборки через FiftyOne (десятки–сотни МБ при дефолтных лимитах).
Сгенерированные папки с изображениями в git не входят — см. корневой ``.gitignore``.
Загрузка идёт **порциями** (``--chunk-size``): файлы появляются в ``binary/`` после каждой порции,
а не только после скачивания тысяч кадров сразу.

**Cursor / VS Code:** каталоги ``binary/birds`` и т.д. могут быть скрыты в дереве из‑за
``.gitignore`` — смотрите ``ls binary/birds/train/images`` в терминале или включите показ
исключённых файлов.

**Грызуны:** только Open Images V6, класс ``Squirrel``. Нужен доступ к ``storage.googleapis.com``
(метаданные и часть загрузок). Флаг ``--rodent-validation-only`` не качает огромный train CSV.
При обрывах SSL — VPN/другая сеть или скопировать готовый ``~/fiftyone/`` с машины, где OID уже скачан.

Пример::

    cd scripts/datasets
    python3 -m venv .venv-detector && . .venv-detector/bin/activate
    pip install fiftyone pyyaml
    python3 bootstrap_detector_yolo.py --birds-train 300 --birds-val 100 \\
        --rodent-train 200 --rodent-val 80 \\
        --background-train 250 --background-val 150

Затем из корня репозитория::

    make dataset-merge-three-class
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def _binary(root: Path) -> Path:
    """Корень ``binary/`` рядом со скриптами: ``scripts/datasets/binary``."""
    return root / "binary"


def _ensure_layout(root: Path) -> None:
    base = _binary(root)
    for sub in ("birds", "rodent", "background"):
        for split in ("train", "val"):
            (base / sub / split / "images").mkdir(parents=True, exist_ok=True)
            (base / sub / split / "labels").mkdir(parents=True, exist_ok=True)


def _detections(sample) -> list:
    """FiftyOne: COCO/OID обычно кладут боксы в ``ground_truth``."""
    gt = getattr(sample, "ground_truth", None)
    if gt is None:
        return []
    return list(gt.detections) if gt.detections else []


def _write_yolo_label(path: Path, class_id: int, detections) -> None:
    lines = []
    for det in detections:
        x, y, w, h = det.bounding_box
        xc = x + w / 2.0
        yc = y + h / 2.0
        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
    path.write_text("".join(lines), encoding="utf-8")


def _unique_copy(src: Path, dst_dir: Path) -> Path:
    """Избегаем коллизий имён между сплитами/источниками."""
    name = src.name
    dst = dst_dir / name
    if not dst.exists():
        shutil.copy2(src, dst)
        return dst
    stem, suf = Path(name).stem, Path(name).suffix
    for i in range(1, 10_000):
        alt = dst_dir / f"{stem}_{i}{suf}"
        if not alt.exists():
            shutil.copy2(src, alt)
            return alt
    raise OSError("too many name collisions")


def _bootstrap_birds(root: Path, train_max: int, val_max: int, *, chunk_size: int) -> None:
    import fiftyone as fo
    import fiftyone.zoo as foz

    for split_name, lim, tag in (
        ("train", train_max, "train"),
        ("validation", val_max, "val"),
    ):
        images_dir = _binary(root) / "birds" / tag / "images"
        labels_dir = _binary(root) / "birds" / tag / "labels"
        total = 0
        seed = 0
        while total < lim:
            take = min(chunk_size, lim - total)
            print(f"[birds] COCO 2017 {split_name} bird — chunk size={take}, seed={seed}, have {total}/{lim}")
            ds = foz.load_zoo_dataset(
                "coco-2017",
                split=split_name,
                label_types=["detections"],
                classes=["bird"],
                max_samples=take,
                shuffle=True,
                seed=seed,
            )
            n_chunk = 0
            for sample in ds:
                birds = [d for d in _detections(sample) if d.label == "bird"]
                if not birds:
                    continue
                dst_img = _unique_copy(Path(sample.filepath), images_dir)
                stem = dst_img.stem
                _write_yolo_label(labels_dir / f"{stem}.txt", 0, birds)
                n_chunk += 1
                total += 1
                if total >= lim:
                    break
            fo.delete_dataset(ds.name)
            seed += 1
            if n_chunk == 0:
                print(f"[birds] предупреждение: пустой chunk для {split_name}, прерываем сплит")
                break
        print(f"[birds] → {tag}/: {total} images")


def _bootstrap_rodents_validation_only(
    root: Path, train_max: int, val_max: int, *, chunk_size: int
) -> None:
    """Только split ``validation`` Open Images: меньше метаданных, без гигантского train CSV."""
    import fiftyone as fo
    import fiftyone.zoo as foz

    images_train = _binary(root) / "rodent" / "train" / "images"
    labels_train = _binary(root) / "rodent" / "train" / "labels"
    images_val = _binary(root) / "rodent" / "val" / "images"
    labels_val = _binary(root) / "rodent" / "val" / "labels"
    got_train = 0
    got_val = 0
    seed = 0
    total_need = train_max + val_max
    while got_train + got_val < total_need:
        take = min(chunk_size, total_need - got_train - got_val)
        print(
            f"[rodent] Open Images V6 validation-only Squirrel — chunk size={take}, "
            f"seed={seed}, train {got_train}/{train_max}, val {got_val}/{val_max}"
        )
        ds = foz.load_zoo_dataset(
            "open-images-v6",
            split="validation",
            label_types=["detections"],
            classes=["Squirrel"],
            max_samples=take,
            only_matching=True,
            shuffle=True,
            seed=seed,
        )
        n_chunk = 0
        for sample in ds:
            sq = [d for d in _detections(sample) if d.label == "Squirrel"]
            if not sq:
                continue
            if got_train < train_max:
                dst_img = _unique_copy(Path(sample.filepath), images_train)
                stem = dst_img.stem
                _write_yolo_label(labels_train / f"{stem}.txt", 0, sq)
                got_train += 1
            elif got_val < val_max:
                dst_img = _unique_copy(Path(sample.filepath), images_val)
                stem = dst_img.stem
                _write_yolo_label(labels_val / f"{stem}.txt", 0, sq)
                got_val += 1
            n_chunk += 1
            if got_train >= train_max and got_val >= val_max:
                break
        fo.delete_dataset(ds.name)
        seed += 1
        if n_chunk == 0:
            print("[rodent] предупреждение: пустой chunk (validation-only), прерываем")
            break
    print(f"[rodent] → train/: {got_train} images (validation split)")
    print(f"[rodent] → val/: {got_val} images (validation split)")


def _bootstrap_rodents(
    root: Path,
    train_max: int,
    val_max: int,
    *,
    chunk_size: int,
    validation_only: bool = False,
) -> None:
    if validation_only:
        _bootstrap_rodents_validation_only(root, train_max, val_max, chunk_size=chunk_size)
        return

    import fiftyone as fo
    import fiftyone.zoo as foz

    for split_name, lim, tag in (
        ("train", train_max, "train"),
        ("validation", val_max, "val"),
    ):
        images_dir = _binary(root) / "rodent" / tag / "images"
        labels_dir = _binary(root) / "rodent" / tag / "labels"
        total = 0
        seed = 0
        while total < lim:
            take = min(chunk_size, lim - total)
            print(f"[rodent] Open Images V6 {split_name} Squirrel — chunk size={take}, seed={seed}, have {total}/{lim}")
            ds = foz.load_zoo_dataset(
                "open-images-v6",
                split=split_name,
                label_types=["detections"],
                classes=["Squirrel"],
                max_samples=take,
                only_matching=True,
                shuffle=True,
                seed=seed,
            )
            n_chunk = 0
            for sample in ds:
                sq = [d for d in _detections(sample) if d.label == "Squirrel"]
                if not sq:
                    continue
                dst_img = _unique_copy(Path(sample.filepath), images_dir)
                stem = dst_img.stem
                _write_yolo_label(labels_dir / f"{stem}.txt", 0, sq)
                n_chunk += 1
                total += 1
                if total >= lim:
                    break
            fo.delete_dataset(ds.name)
            seed += 1
            if n_chunk == 0:
                print(f"[rodent] предупреждение: пустой chunk для {split_name}, прерываем сплит")
                break
        print(f"[rodent] → {tag}/: {total} images")


def _collect_no_bird_background(
    root: Path,
    *,
    coco_split: str,
    pool: int,
    target: int,
    out_tag: str,
    scan_chunk: int,
) -> int:
    import fiftyone as fo
    import fiftyone.zoo as foz

    images_dir = _binary(root) / "background" / out_tag / "images"
    labels_dir = _binary(root) / "background" / out_tag / "labels"
    seen_fp: set[str] = set()
    n = 0
    scanned = 0
    seed = 0
    print(
        f"[background] COCO {coco_split} → {out_tag}/: цель {target} кадров без bird, "
        f"бюджет просмотра ≤{pool}, порции по {scan_chunk}",
    )
    while n < target and scanned < pool:
        chunk = min(scan_chunk, pool - scanned)
        print(f"[background] chunk seed={seed}, samples={chunk}, уже принято {n}/{target}")
        ds = foz.load_zoo_dataset(
            "coco-2017",
            split=coco_split,
            label_types=["detections"],
            max_samples=chunk,
            shuffle=True,
            seed=seed,
        )
        for sample in ds:
            fp = sample.filepath
            if fp in seen_fp:
                continue
            seen_fp.add(fp)
            has_bird = any(d.label == "bird" for d in _detections(sample))
            if has_bird:
                continue
            dst_img = _unique_copy(Path(sample.filepath), images_dir)
            stem = dst_img.stem
            (labels_dir / f"{stem}.txt").write_text("", encoding="utf-8")
            n += 1
            if n >= target:
                break
        fo.delete_dataset(ds.name)
        scanned += chunk
        seed += 1
    print(f"[background] → {out_tag}/: {n} images (empty labels)")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Корень выхода (по умолчанию scripts/datasets)",
    )
    ap.add_argument("--birds-train", type=int, default=400)
    ap.add_argument("--birds-val", type=int, default=120)
    ap.add_argument("--rodent-train", type=int, default=300)
    ap.add_argument("--rodent-val", type=int, default=80)
    ap.add_argument("--background-train", type=int, default=280)
    ap.add_argument("--background-val", type=int, default=120)
    ap.add_argument("--background-train-pool", type=int, default=12000, help="Сколько кадров COCO train просмотреть")
    ap.add_argument("--background-val-pool", type=int, default=8000, help="Сколько кадров COCO val просмотреть")
    ap.add_argument(
        "--chunk-size",
        type=int,
        default=35,
        help="Сколько образцов подряд запрашивать у FiftyOne за один проход (меньше — раньше появятся файлы на диске)",
    )
    ap.add_argument(
        "--bg-scan-chunk",
        type=int,
        default=600,
        help="Размер порции при сканировании COCO для фона (без единого огромного prefetch)",
    )
    ap.add_argument("--skip-birds", action="store_true")
    ap.add_argument("--skip-rodents", action="store_true")
    ap.add_argument("--skip-background", action="store_true")
    ap.add_argument(
        "--rodent-validation-only",
        action="store_true",
        help="Грызуны только из сплита validation Open Images (без скачивания огромного train CSV)",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    try:
        import fiftyone as fo  # noqa: F401
        import fiftyone.zoo as foz  # noqa: F401
    except ImportError:
        print("Установите: pip install fiftyone", file=sys.stderr)
        return 2

    _ensure_layout(root)

    ch = max(5, args.chunk_size)
    bg_ch = max(100, args.bg_scan_chunk)

    if not args.skip_birds:
        _bootstrap_birds(root, args.birds_train, args.birds_val, chunk_size=ch)
    if not args.skip_rodents:
        _bootstrap_rodents(
            root,
            args.rodent_train,
            args.rodent_val,
            chunk_size=ch,
            validation_only=args.rodent_validation_only,
        )
    if not args.skip_background:
        _collect_no_bird_background(
            root,
            coco_split="train",
            pool=args.background_train_pool,
            target=args.background_train,
            out_tag="train",
            scan_chunk=bg_ch,
        )
        _collect_no_bird_background(
            root,
            coco_split="validation",
            pool=args.background_val_pool,
            target=args.background_val,
            out_tag="val",
            scan_chunk=bg_ch,
        )

    print("\nГотово. Дальше из корня репозитория: make dataset-merge-three-class")
    b = _binary(root)
    print(f"Данные: {b}/birds, {b}/rodent, {b}/background")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
