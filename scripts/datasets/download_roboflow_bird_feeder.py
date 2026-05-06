#!/usr/bin/env python3
"""
Скачивание датасета **Bird-Feeder** с Roboflow (формат YOLOv11) и импорт в
``datasets/new/detector/binary/birds`` (класс 0), как у ``import_roboflow_bird_feeder_birds.py``.

**Ключ API только из окружения** ``ROBOFLOW_API_KEY``. Не вставляйте ключ в код,
не коммитьте его и не публикуйте в чатах — при утечке сразу отзовите ключ в
https://app.roboflow.com/ и создайте новый.

Зависимость::

    pip install roboflow

Пример::

    export ROBOFLOW_API_KEY='ваш_ключ'
    python3 scripts/datasets/download_roboflow_bird_feeder.py \\
      --root "$(pwd)/datasets/new/detector"

Только скачать в ``datasets/downloads/…`` без импорта::

    python3 scripts/datasets/download_roboflow_bird_feeder.py --skip-import

Затем: ``make dataset-merge-three-class``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def _load_rf_import_helpers():
    """Имя файла ``import_*.py`` не является валидным именем модуля для ``import``."""
    imp_path = Path(__file__).resolve().parent / "import_roboflow_bird_feeder_birds.py"
    spec = importlib.util.spec_from_file_location("_bird_feeder_rf_imp", imp_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "datasets" / "new" / "detector",
        help="Корень ETL (binary/birds)",
    )
    ap.add_argument("--workspace", type=str, default="meproject-pcsly")
    ap.add_argument("--project", type=str, default="bird-feeder-hhjks")
    ap.add_argument("--version", type=int, default=3)
    ap.add_argument(
        "--download-dir",
        type=Path,
        default=None,
        help="Куда Roboflow распакует датасет (по умолчанию datasets/downloads/roboflow_<project>_v<N>)",
    )
    ap.add_argument(
        "--skip-import",
        action="store_true",
        help="Только скачать, не вызывать import_roboflow_bird_feeder_birds.py",
    )
    ap.add_argument(
        "--prefix",
        type=str,
        default="rfbf_",
        help="Префикс файлов при импорте",
    )
    args = ap.parse_args()

    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        print(
            "Задайте переменную окружения ROBOFLOW_API_KEY "
            "(Roboflow → Settings → API).",
            file=sys.stderr,
        )
        return 2

    try:
        from roboflow import Roboflow
    except ImportError:
        print("Установите: pip install roboflow", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent.parent
    if args.download_dir is not None:
        download_dir = args.download_dir.resolve()
    else:
        slug = args.project.replace("/", "-")
        download_dir = repo_root / "datasets" / "downloads" / f"roboflow_{slug}_v{args.version}"
    download_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Roboflow: workspace={args.workspace!r} project={args.project!r} "
        f"version={args.version} → {download_dir}",
        flush=True,
    )

    rf = Roboflow(api_key=api_key)
    proj = rf.workspace(args.workspace).project(args.project)
    ver = proj.version(args.version)
    # location: каталог для распаковки (Roboflow создаёт подпапку проекта).
    ver.download("yolov11", location=str(download_dir))

    rf_imp = _load_rf_import_helpers()
    yolo_root = rf_imp.find_roboflow_yolo_export_root(download_dir)
    if not (yolo_root / "train" / "images").is_dir():
        print(
            f"После скачивания не найден train/images под {download_dir} "
            f"(пробовали корень {yolo_root}).",
            file=sys.stderr,
        )
        return 2

    print(f"YOLO export root: {yolo_root}", flush=True)

    if args.skip_import:
        print("Импорт пропущен (--skip-import). Дальше вручную:")
        print(
            f"  python3 scripts/datasets/import_roboflow_bird_feeder_birds.py "
            f"--root {args.root.resolve()} --extracted-dir {yolo_root}",
        )
        return 0

    imp = Path(__file__).resolve().parent / "import_roboflow_bird_feeder_birds.py"
    cmd = [
        sys.executable,
        str(imp),
        "--root",
        str(args.root.resolve()),
        "--extracted-dir",
        str(yolo_root),
        "--prefix",
        args.prefix,
    ]
    proc = subprocess.run(cmd)
    return int(proc.returncode != 0)


if __name__ == "__main__":
    raise SystemExit(main())
