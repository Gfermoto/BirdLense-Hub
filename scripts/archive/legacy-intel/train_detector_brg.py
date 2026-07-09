#!/usr/bin/env python3
"""Обучение детектора Bird / Rodent / Background (Ultralytics YOLO detect).

По умолчанию используется ``datasets/new/detector/yolo/dataset.yaml``; в YAML дописывается
поле ``path`` рядом со скриптом, чтобы пути ``train/`` / ``val/`` резолвились одинаково локально
и в CI.

Двухэтапный режим (как в docs/ML_DETECTOR_COLAB.ru.md): freeze backbone → полное дообучение.
Экспорт OpenVINO 640×640 — под путь ``processor.models.binary_openvino`` в приложении.

Примеры::

    pip install ultralytics torch  # или .venv проекта

    # с нуля от yolo11n.pt (скачивается один раз Ultralytics)
    python3 scripts/train_detector_brg.py --device 0

    # дообучение от текущих весов хаба / чекпоинта
    python3 scripts/train_detector_brg.py --weights /path/to/bl_best.pt --device 0

    # один этап, меньше эпох
    python3 scripts/train_detector_brg.py --single --epochs 80 --freeze 10

    # только продолжить прерванный ран
    python3 scripts/train_detector_brg.py --resume runs/brg_ov640/stage2/weights/last.pt

    # после обучения: IR рядом с best.pt рана «stage2»
    python3 scripts/train_detector_brg.py --export-openvino-only runs/.../stage2/weights/best.pt
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_data_yaml(data_arg: Path) -> Path:
    p = data_arg.expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"нет dataset yaml: {p}")
    # В репозитории path часто опущен; Ultralytics резолвит split-ы относительно каталога yaml.
    with p.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["path"] = str(p.parent)
    out = p.parent / "_train_resolved_dataset.yaml"
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    return out


def _pick_device(spec: str | None):
    if spec is None:
        try:
            import torch

            if torch.cuda.is_available():
                return 0
            if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"
    if spec.lower() in ("cuda", "gpu"):
        return 0
    return spec


def _export_openvino(best_pt: Path, imgsz: int) -> Path:
    from ultralytics import YOLO

    m = YOLO(str(best_pt))
    paths = m.export(format="openvino", imgsz=imgsz, simplify=True)
    if isinstance(paths, str):
        return Path(paths).resolve().parent if Path(paths).is_file() else Path(paths).resolve()
    lst = paths[0] if paths else ""
    pt = Path(str(lst))
    return pt.resolve().parent if pt.is_file() else pt.resolve()


def _train_run(
    data_yaml_resolved: Path,
    weights: str | Path,
    project: Path,
    name: str,
    epochs: int,
    imgsz: int,
    batch: int,
    device,
    freeze: int | None,
    lr0: float | None,
    patience: int,
    cache: str | bool,
    workers: int,
):
    from ultralytics import YOLO

    kwargs = dict(
        data=str(data_yaml_resolved),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        patience=patience,
        cache=cache,
        project=str(project),
        name=name,
        exist_ok=True,
        device=device,
        workers=workers,
    )
    if freeze is not None:
        kwargs["freeze"] = freeze
    if lr0 is not None:
        kwargs["lr0"] = lr0
    model = YOLO(str(weights))
    model.train(**kwargs)
    best = Path(project, name, "weights", "best.pt").resolve()
    last = Path(project, name, "weights", "last.pt").resolve()
    if not best.is_file():
        raise FileNotFoundError(f"ожидался checkpoint: {best}")
    return best, last


def main() -> int:
    root = _repo_root()
    default_data = root / "datasets/new/detector/yolo/dataset.yaml"
    default_project = root / "datasets/new/detector/runs"

    ap = argparse.ArgumentParser(description="Обучение BRG YOLO11 (detect) + опционально OpenVINO.")
    ap.add_argument("--data", type=Path, default=default_data, help="dataset.yaml (YOLO detect)")
    ap.add_argument("--weights", type=str, default="yolo11n.pt", help="стартовые веса .pt или имя из Ultralytics")
    ap.add_argument("--project", type=Path, default=default_project, help="каталог ранов Ultralytics")
    ap.add_argument("--run-name", type=str, default="brg_ov640", help="префикс имени подпапок stage1/stage2")
    ap.add_argument("--device", type=str, default=None, help="0, cpu, mps, cuda; по умолчанию авто")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cache", type=str, default="disk", choices=("ram", "disk"))
    ap.add_argument("--no-cache", action="store_true", help="не кэшировать датасет (медленнее, меньше RAM/диск)")
    ap.add_argument("--patience", type=int, default=25)
    ap.add_argument("--single", action="store_true", help="один этап вместо freeze→full")
    ap.add_argument("--epochs", type=int, default=None, help="для --single; иначе игнор (см. stage эпохи)")
    ap.add_argument("--freeze", type=int, default=10, help="для первого этапа / --single")
    ap.add_argument("--epochs-stage1", type=int, default=40)
    ap.add_argument("--epochs-stage2", type=int, default=60)
    ap.add_argument("--lr0-stage2", type=float, default=0.001)
    ap.add_argument("--resume", type=Path, default=None, help="last.pt — только resume=True, без новых аргументов")
    ap.add_argument("--export-openvino", action="store_true", help="после обучения экспорт final best→OpenVINO")
    ap.add_argument(
        "--export-openvino-only",
        type=Path,
        default=None,
        help="только экспорт готового best.pt в OpenVINO (без train)",
    )
    ap.add_argument("--copy-to-processor", action="store_true", help="скопировать best.pt + IR в app/processor/.../weights")
    args = ap.parse_args()

    if args.export_openvino_only is not None:
        p = args.export_openvino_only.expanduser().resolve()
        if not p.is_file():
            print(f"Нет файла: {p}", file=sys.stderr)
            return 1
        ov_dir = _export_openvino(p, args.imgsz)
        print("OpenVINO:", ov_dir)
        return 0

    if args.resume is not None:
        r = args.resume.expanduser().resolve()
        if not r.is_file():
            print(f"Нет checkpoint: {r}", file=sys.stderr)
            return 1
        from ultralytics import YOLO

        YOLO(str(r)).train(resume=True)
        print("resume завершён (см. каталог рана Ultralytics из чекпоинта)")
        return 0

    data_resolved = _ensure_data_yaml(args.data)
    project = args.project.expanduser().resolve()
    project.mkdir(parents=True, exist_ok=True)
    device = _pick_device(args.device)

    if args.single:
        epochs = args.epochs if args.epochs is not None else 80
        best, _ = _train_run(
            data_resolved,
            args.weights,
            project,
            f"{args.run_name}_single",
            epochs=epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=device,
            freeze=args.freeze,
            lr0=None,
            patience=args.patience,
            cache=False if args.no_cache else args.cache,
            workers=args.workers,
        )
        final_best = best
    else:
        s1 = f"{args.run_name}_stage1_freeze{args.freeze}"
        best1, _ = _train_run(
            data_resolved,
            args.weights,
            project,
            s1,
            epochs=args.epochs_stage1,
            imgsz=args.imgsz,
            batch=args.batch,
            device=device,
            freeze=args.freeze,
            lr0=None,
            patience=args.patience,
            cache=False if args.no_cache else args.cache,
            workers=args.workers,
        )
        s2 = f"{args.run_name}_stage2_full"
        best2, _ = _train_run(
            data_resolved,
            best1,
            project,
            s2,
            epochs=args.epochs_stage2,
            imgsz=args.imgsz,
            batch=args.batch,
            device=device,
            freeze=None,
            lr0=args.lr0_stage2,
            patience=args.patience,
            cache=False if args.no_cache else args.cache,
            workers=args.workers,
        )
        final_best = best2

    print("best.pt:", final_best)
    ov_dir: Path | None = None
    if args.export_openvino:
        ov_dir = _export_openvino(final_best, args.imgsz)
        print("OpenVINO:", ov_dir)

    if args.copy_to_processor:
        proc_w = root / "app/processor/models/detection/weights"
        proc_w.mkdir(parents=True, exist_ok=True)
        dst_pt = proc_w / "best.pt"
        shutil.copy2(final_best, dst_pt)
        print("скопировано:", dst_pt)
        if ov_dir is not None and ov_dir.is_dir():
            dst_ir = proc_w / "best_openvino_model"
            if dst_ir.exists():
                shutil.rmtree(dst_ir)
            shutil.copytree(ov_dir, dst_ir)
            print("скопировано IR:", dst_ir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
