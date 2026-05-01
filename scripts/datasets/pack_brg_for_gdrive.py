#!/usr/bin/env python3
"""Упаковать ``scripts/datasets/brg`` в ZIP под загрузку на Google Drive / облако.

В архиве только то, что нужно для обучения YOLO detect: ``dataset.yaml``, сплиты
``train|val|test`` с ``images/`` и ``labels/``. Служебные JSON (dedupe, merge manifest)
не включаются. Файлы ``*:Zone.Identifier`` пропускаются.

Выход по умолчанию: ``datasets/BirdLense_detector_brg_YYYYMMDD_HHMMSS.zip`` в корне репозитория
(каталог ``datasets/`` в ``.gitignore``).

Пример::

    python3 scripts/datasets/pack_brg_for_gdrive.py
    python3 scripts/datasets/pack_brg_for_gdrive.py --out /tmp/brg.zip
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_README = """BirdLense — датасет детектора (Bird / Rodent / Background), YOLO format.

Структура после распаковки:
  brg/dataset.yaml
  brg/train/images, brg/train/labels
  brg/val/images, brg/val/labels
  brg/test/images, brg/test/labels (если есть)

Google Drive: часто кладут этот ZIP и чекпоинт детектора в одну папку, например:
  MyDrive/BirdLense_Detector/<этот_zip>.zip
  MyDrive/BirdLense_Detector/bl_best.pt   (текущие веса YOLO11n с хаба)

Colab (пример):
  from google.colab import drive
  drive.mount('/content/drive')
  ROOT = '/content/drive/MyDrive/BirdLense_Detector'
  !unzip -q "$ROOT/BirdLense_detector_brg_*.zip" -d /content/brg_unpack
  # дальше data=/content/brg_unpack/brg/dataset.yaml model=$ROOT/bl_best.pt

Обучение (Ultralytics), с абсолютными путями к yaml и ckpt:
  yolo detect train data=/path/to/brg/dataset.yaml model=/path/to/bl_best.pt \\
    epochs=100 imgsz=640 freeze=10

Полный сценарий (два этапа, OpenVINO): docs/ML_DETECTOR_COLAB.ru.md

Классы в yaml: 0 Bird, 1 Rodent, 2 Background. Пустые .txt у фоновых кадров — норма.

Происхождение (типичный mix): COCO/OID bootstrap, Roboflow Bird-Feeder (CC BY 4.0 — проверьте
атрибуцию при публикации весов), локальные фоны с камер. Не перепродавайте чужие данные
вне их лицензий.
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _should_skip(path: Path) -> bool:
    name = path.name
    if name.endswith(":Zone.Identifier") or "Zone.Identifier" in name:
        return True
    if path.suffix.lower() == ".json" and name in (
        "dedupe_report.json",
        "merge_manifest.json",
    ):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--brg-dir",
        type=Path,
        default=None,
        help="Каталог brg (по умолчанию: <repo>/scripts/datasets/brg)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Путь к .zip (по умолчанию datasets/BirdLense_detector_brg_<UTC>.zip)",
    )
    args = ap.parse_args()

    repo = _repo_root()
    brg = (args.brg_dir or (repo / "scripts" / "datasets" / "brg")).resolve()
    if not brg.is_dir():
        print(f"brg not found: {brg}", file=sys.stderr)
        return 2
    yaml_path = brg / "dataset.yaml"
    if not yaml_path.is_file():
        print(f"missing dataset.yaml: {yaml_path}", file=sys.stderr)
        return 2

    out_dir = repo / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    out_zip = (args.out or (out_dir / f"BirdLense_detector_brg_{stamp}.zip")).resolve()

    added = 0
    skipped = 0
    with zipfile.ZipFile(
        out_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as zf:
        zi_readme = zipfile.ZipInfo("brg/README_UPLOAD.txt")
        zi_readme.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi_readme, _README.encode("utf-8"))
        added += 1

        for path in sorted(brg.rglob("*")):
            if not path.is_file():
                continue
            if _should_skip(path):
                skipped += 1
                continue
            rel = path.relative_to(brg)
            arcname = Path("brg") / rel
            zf.write(path, arcname.as_posix())
            added += 1

    size_mb = out_zip.stat().st_size / (1024 * 1024)
    print(f"ZIP -> {out_zip}")
    print(f"Members written: {added} (skipped rules: {skipped}), size ~{size_mb:.1f} MiB")
    print("Загрузите файл на Google Drive; для Colab смонтируйте Drive и укажите путь к zip/unzip.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
