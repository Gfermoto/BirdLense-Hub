#!/usr/bin/env python3
"""Inspect Ornimetrics / Trapper weight files for embedded class labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def extract_trapper_pt(pt_path: Path) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(pt_path), task="detect")
    names = {int(k): str(v) for k, v in model.names.items()}
    return {
        "source": "ultralytics.YOLO.names",
        "path": str(pt_path.resolve()),
        "num_classes": len(names),
        "names": names,
    }


def inspect_inat_onnx(onnx_path: Path) -> dict:
    import onnx
    from onnx import numpy_helper

    model = onnx.load(str(onnx_path), load_external_data=True)
    meta = {p.key: p.value for p in model.metadata_props}
    outputs = []
    for out in model.graph.output:
        dims = [d.dim_value or d.dim_param for d in out.type.tensor_type.shape.dim]
        outputs.append({"name": out.name, "shape": dims})
    label_init = []
    for init in model.graph.initializer:
        low = init.name.lower()
        if any(k in low for k in ("label", "class", "name", "species")):
            arr = numpy_helper.to_array(init)
            label_init.append(
                {"name": init.name, "shape": list(arr.shape), "dtype": str(arr.dtype)}
            )
    return {
        "source": "onnx.graph inspection",
        "path": str(onnx_path.resolve()),
        "producer": f"{model.producer_name} {model.producer_version}".strip(),
        "metadata_props": meta,
        "outputs": outputs,
        "label_like_initializers": label_init,
        "classes_embedded": False,
        "note": (
            "species_classifier_inat.onnx has no string labels in metadata or graph; "
            "HF never published species_classifier_inat.json (git history checked). "
            "Use generate_ornimetrics_inat_json.py with an authoritative 302-line list."
        ),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--trapper-pt",
        type=Path,
        default=root / "app/processor/models/detection/weights/trapper_ai_v02_2024.pt",
    )
    ap.add_argument(
        "--inat-onnx",
        type=Path,
        default=root
        / "app/processor/models/classification/ornimetrics/species_classifier_inat.onnx",
    )
    args = ap.parse_args()
    report: dict = {}
    if args.trapper_pt.is_file():
        report["trapper"] = extract_trapper_pt(args.trapper_pt)
    else:
        report["trapper"] = {"error": "missing", "path": str(args.trapper_pt)}
    if args.inat_onnx.is_file():
        report["inat"] = inspect_inat_onnx(args.inat_onnx)
    else:
        report["inat"] = {"error": "missing", "path": str(args.inat_onnx)}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
