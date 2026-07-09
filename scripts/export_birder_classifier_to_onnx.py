#!/usr/bin/env python3
"""Export Birder EU .pt weights to ONNX for Orin ONNX Runtime (CUDA EP)."""

from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_VARIANT = "convnext_v2_tiny_eu-common256px"


def export_variant(variant: str, classification_root: Path) -> Path:
    import torch

    model_dir = classification_root / variant
    pt_path = model_dir / f"{variant}.pt"
    if not pt_path.is_file():
        raise FileNotFoundError(
            f"Missing {pt_path} — run: python3 scripts/download_birder_classifier.py",
        )

    import birder

    net, info, _ = birder.load_pretrained_model_and_transform(variant, inference=True)
    net.eval()
    size = int(info.signature["inputs"][0]["data_shape"][-1])
    dummy = torch.randn(1, 3, size, size, dtype=torch.float32)
    onnx_path = model_dir / f"{variant}.onnx"

    torch.onnx.export(
        net,
        dummy,
        str(onnx_path),
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=18,
    )
    print(f"OK {onnx_path} (input {size}x{size})")
    return onnx_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument(
        "--dest",
        type=Path,
        default=REPO / "app" / "processor" / "models" / "classification",
    )
    args = parser.parse_args()
    export_variant(args.variant, args.dest)


if __name__ == "__main__":
    main()
