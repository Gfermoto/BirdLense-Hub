#!/usr/bin/env python3
"""
Экспорт best_NABirds.pt → OpenVINO IR (``best_NABirds_openvino_model/``).

Ultralytics требует суффикс каталога ``*_openvino_model`` — иначе AutoBackend не загрузит IR.

Не включать OV в прод без validate_ov_parity.py (parity <5%).

Пример:
  python3 scripts/export_nabirds_to_openvino.py --imgsz 640 --precision fp32
  python3 scripts/validate_ov_parity.py --ov-dir app/processor/models/detection/weights/nabirds_openvino_v1
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_pt(processor_root: Path) -> Path:
    return processor_root / "models/detection/weights/best_NABirds.pt"


def _export_openvino(
    pt_path: Path,
    *,
    imgsz: int,
    half: bool,
    simplify: bool,
    dynamic: bool,
) -> Path:
    from ultralytics import YOLO

    m = YOLO(str(pt_path))
    paths = m.export(
        format="openvino",
        imgsz=int(imgsz),
        half=bool(half),
        simplify=bool(simplify),
        dynamic=bool(dynamic),
    )
    if isinstance(paths, str):
        p = Path(paths)
        return p.parent.resolve() if p.is_file() else p.resolve()
    lst = paths[0] if paths else ""
    p = Path(str(lst))
    return p.parent.resolve() if p.is_file() else p.resolve()


def _find_bundle(pt_path: Path) -> Path | None:
    parent = pt_path.parent
    expected = parent / f"{pt_path.stem}_openvino_model"
    if expected.is_dir() and list(expected.glob("*.xml")):
        return expected
    for candidate in sorted(parent.iterdir(), key=lambda x: x.name):
        if candidate.is_dir() and candidate.name.endswith("_openvino_model"):
            if list(candidate.glob("*.xml")):
                return candidate
    return None


def main() -> int:
    root = _repo_root()
    processor_root = root / "app" / "processor"
    # Ultralytics AutoBackend: каталог должен оканчиваться на ``_openvino_model``.
    default_out = processor_root / "models/detection/weights/best_NABirds_openvino_model"

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pt",
        type=Path,
        default=_default_pt(processor_root),
        help="Путь к best_NABirds.pt",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=default_out,
        help="Целевой каталог IR (должен оканчиваться на _openvino_model)",
    )
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument(
        "--precision",
        choices=("fp32", "fp16"),
        default="fp32",
        help="fp32 — эталон parity; fp16 — только после успешного fp32",
    )
    ap.add_argument("--dynamic", action="store_true", help="dynamic batch (обычно false)")
    ap.add_argument("--no-simplify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pt = args.pt.resolve()
    if not pt.is_file():
        print(json.dumps({"error": "pt_missing", "path": str(pt)}), file=sys.stderr)
        return 2

    half = args.precision == "fp16"
    report: dict = {
        "pt": str(pt),
        "out_dir": str(args.out_dir.resolve()),
        "imgsz": int(args.imgsz),
        "precision": args.precision,
        "half": half,
        "simplify": not args.no_simplify,
        "dynamic": bool(args.dynamic),
    }

    if args.dry_run:
        print(json.dumps({**report, "dry_run": True}, indent=2))
        return 0

    try:
        from ultralytics import YOLO  # noqa: F401
    except ImportError:
        print(json.dumps({"error": "ultralytics_missing"}), file=sys.stderr)
        return 2

    found = _export_openvino(
        pt,
        imgsz=args.imgsz,
        half=half,
        simplify=not args.no_simplify,
        dynamic=bool(args.dynamic),
    )
    bundle = _find_bundle(pt) or found
    if bundle is None or not list(bundle.glob("*.xml")):
        print(json.dumps({"error": "export_no_xml", **report}), file=sys.stderr)
        return 1

    target = args.out_dir.resolve()
    bundle = bundle.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if bundle.resolve() != target.resolve():
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(bundle, target)
    elif not target.exists():
        raise FileNotFoundError(f"export bundle missing: {bundle}")
    # Ultralytics OpenVINO loader ожидает пару best.xml / best.bin в каталоге.
    for xml in sorted(target.glob("*.xml")):
        bin_candidates = sorted(target.glob(xml.stem + ".*"))
        bin_path = next((p for p in bin_candidates if p.suffix == ".bin"), None)
        if bin_path is None:
            continue
        canonical_xml = target / "best.xml"
        canonical_bin = target / "best.bin"
        if xml.resolve() != canonical_xml.resolve():
            shutil.copy2(xml, canonical_xml)
        if bin_path.resolve() != canonical_bin.resolve():
            shutil.copy2(bin_path, canonical_bin)
        break

    meta_path = target / "export_report.json"
    report.update(
        {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source_bundle": str(bundle),
            "xml_files": [p.name for p in sorted(target.glob("*.xml"))],
            "next_step": "python3 scripts/validate_ov_parity.py --ov-dir " + str(target),
        }
    )
    meta_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
