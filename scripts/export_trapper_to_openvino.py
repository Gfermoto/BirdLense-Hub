#!/usr/bin/env python3
"""
Скачать OSCF/TrapperAI-v02.2024 → trapper_ai_v02_2024.pt и экспорт OpenVINO IR.

Каталог IR: ``trapper_ai_v02_2024_openvino_model/`` (суффикс ``_openvino_model`` для Ultralytics).
Внутри: ``trapper_ai_v02_2024.{xml,bin}`` + ``best.{xml,bin}`` (loader Ultralytics).

Пример:
  python3 scripts/export_trapper_to_openvino.py --imgsz 704 --precision fp16
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HF_REPO = "OSCF/TrapperAI-v02.2024"
HF_FILENAME = "TrapperAI-v02.2024-YOLOv8-m.pt"
MODEL_STEM = "trapper_ai_v02_2024"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _download_pt(dest: Path) -> Path:
    from huggingface_hub import hf_hub_download

    src = Path(
        hf_hub_download(repo_id=HF_REPO, filename=HF_FILENAME, local_dir=None)
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest.resolve()


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


def _copy_if_different(src: Path, dst: Path) -> None:
    if src.resolve() == dst.resolve():
        return
    shutil.copy2(src, dst)


def _canonicalize_ir(target: Path, stem: str) -> None:
    xml_files = sorted(target.glob("*.xml"))
    if not xml_files:
        raise FileNotFoundError(f"no xml in {target}")
    named_xml = target / f"{stem}.xml"
    named_bin = target / f"{stem}.bin"
    src_xml = named_xml if named_xml.is_file() else xml_files[0]
    src_bin = target / f"{src_xml.stem}.bin"
    if not src_bin.is_file():
        raise FileNotFoundError(f"no bin for {src_xml}")

    if src_xml.resolve() != named_xml.resolve():
        _copy_if_different(src_xml, named_xml)
    if src_bin.resolve() != named_bin.resolve():
        _copy_if_different(src_bin, named_bin)
    _copy_if_different(src_xml, target / "best.xml")
    _copy_if_different(src_bin, target / "best.bin")


def main() -> int:
    root = _repo_root()
    processor_root = root / "app" / "processor"
    weights = processor_root / "models/detection/weights"
    pt_default = weights / f"{MODEL_STEM}.pt"
    ov_default = weights / f"{MODEL_STEM}_openvino_model"

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pt", type=Path, default=pt_default)
    ap.add_argument("--out-dir", type=Path, default=ov_default)
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--imgsz", type=int, default=1024, help="рекомендация TrapperAI README")
    ap.add_argument("--precision", choices=("fp32", "fp16"), default="fp16")
    ap.add_argument("--dynamic", action="store_true")
    ap.add_argument("--no-simplify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pt = args.pt.resolve()
    target = args.out_dir.resolve()
    half = args.precision == "fp16"
    report: dict = {
        "hf_repo": HF_REPO,
        "hf_filename": HF_FILENAME,
        "pt": str(pt),
        "out_dir": str(target),
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

    if not args.skip_download:
        print(f"Downloading {HF_REPO}/{HF_FILENAME} -> {pt}", file=sys.stderr)
        _download_pt(pt)
    elif not pt.is_file():
        print(json.dumps({"error": "pt_missing", "path": str(pt)}), file=sys.stderr)
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

    target.parent.mkdir(parents=True, exist_ok=True)
    bundle = bundle.resolve()
    if bundle == target.resolve():
        if not bundle.is_dir() or not list(bundle.glob("*.xml")):
            print(json.dumps({"error": "export_bundle_missing", **report}), file=sys.stderr)
            return 1
    else:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(bundle, target)
    _canonicalize_ir(target, MODEL_STEM)

    verify: dict = {"model_loaded": False, "predict_ok": False}
    try:
        m = YOLO(str(target))
        verify["model_loaded"] = True
        import numpy as np

        dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        m.predict(source=dummy, imgsz=args.imgsz, verbose=False)
        verify["predict_ok"] = True
    except Exception as exc:  # noqa: BLE001
        verify["error"] = str(exc)

    report.update(
        {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source_bundle": str(bundle.resolve()),
            "xml_files": sorted(p.name for p in target.glob("*.xml")),
            "bin_files": sorted(p.name for p in target.glob("*.bin")),
            "verify": verify,
        }
    )
    (target / "export_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if verify.get("predict_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
