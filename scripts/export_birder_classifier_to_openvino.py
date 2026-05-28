#!/usr/bin/env python3
"""Export Birder EU classifier to OpenVINO IR (FP16) — flat weights layout."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DEFAULT_VARIANT = "convnext_v2_tiny_eu-common256px"


def export_openvino(variant: str, base: Path, benchmark: bool = False) -> Path:
    import birder
    import openvino as ov
    import torch

    pt_path = base / f"{variant}.pt"
    if not pt_path.is_file():
        raise FileNotFoundError(f"Missing {pt_path}; run scripts/download_birder_classifier.py first")

    out_dir = base / f"{variant}_openvino_model"
    out_dir.mkdir(parents=True, exist_ok=True)

    net, info, _transform = birder.load_pretrained_model_and_transform(variant, inference=True)
    net.eval()
    size = int(info.signature["inputs"][0]["data_shape"][-1])
    dummy = torch.zeros(1, 3, size, size)

    ov_model = ov.convert_model(net, example_input=dummy)
    ov.save_model(ov_model, str(out_dir / "openvino_model.xml"), compress_to_fp16=True)

    for fname in ("class_labels.txt", "birdlense_manifest.json", f"{variant}.json"):
        src = out_dir / fname
        if not src.is_file():
            alt = base / fname if fname.endswith(".json") else None
            if alt and alt.is_file():
                (out_dir / fname).write_bytes(alt.read_bytes())

    manifest_path = out_dir / "birdlense_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"variant": variant, "input_size": size}
    manifest["openvino_xml"] = "openvino_model.xml"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Exported OpenVINO -> {out_dir}")

    if benchmark:
        compiled = ov.Core().compile_model(str(out_dir / "openvino_model.xml"), "CPU")
        inp = np.random.rand(1, 3, size, size).astype(np.float32)
        for _ in range(3):
            compiled([inp])
        t0 = time.perf_counter()
        n = 50
        for _ in range(n):
            compiled([inp])
        ms = (time.perf_counter() - t0) * 1000.0 / n
        print(f"Benchmark CPU: {ms:.2f} ms / crop (n={n}, {size}x{size})")

    return out_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", default=DEFAULT_VARIANT)
    ap.add_argument(
        "--weights-base",
        type=Path,
        default=REPO / "app/processor/models/classification/weights",
    )
    ap.add_argument("--benchmark", action="store_true")
    args = ap.parse_args()
    export_openvino(args.variant, args.weights_base, benchmark=args.benchmark)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
