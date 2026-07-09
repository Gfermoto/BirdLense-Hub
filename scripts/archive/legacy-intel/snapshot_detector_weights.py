#!/usr/bin/env python3
"""
Снимок бинарных весов BRG (best.pt + best_openvino_model/) перед заменой.

Сохраняет копию в ``<processor-root>/models/detection/weights/snapshots/<tag>/``.
По умолчанию tag = UTC timestamp ``YYYYMMDDTHHMMSSZ``.

Пример:
  python3 scripts/snapshot_detector_weights.py
  python3 scripts/snapshot_detector_weights.py --processor-root app/processor --tag before_hf_pull
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--processor-root",
        default="app/processor",
        help="Корень пакета процессора (родитель каталога models/).",
    )
    p.add_argument(
        "--tag",
        default="",
        help="Имя подкаталога в snapshots/ (пусто = UTC timestamp).",
    )
    args = p.parse_args()
    root = Path(args.processor_root).resolve()
    wdir = root / "models" / "detection" / "weights"
    if not wdir.is_dir():
        raise SystemExit(f"weights dir missing: {wdir}")

    tag = (args.tag or "").strip()
    if not tag:
        tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = wdir / "snapshots" / tag
    out.mkdir(parents=True, exist_ok=False)

    pt = wdir / "best.pt"
    ov = wdir / "best_openvino_model"
    copied: list[str] = []
    if pt.is_file():
        shutil.copy2(pt, out / "best.pt")
        copied.append("best.pt")
    if ov.is_dir() and any(ov.glob("*.xml")):
        shutil.copytree(ov, out / "best_openvino_model")
        copied.append("best_openvino_model/")
    if not copied:
        shutil.rmtree(out, ignore_errors=True)
        raise SystemExit(f"nothing to snapshot under {wdir} (need best.pt and/or best_openvino_model)")

    print(f"snapshot_ok {out} ({', '.join(copied)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
