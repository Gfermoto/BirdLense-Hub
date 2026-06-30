#!/usr/bin/env python3
"""Download Birder EU-common weights — ``models/classification/{variant}/``."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

MODELS: dict[str, dict[str, str]] = {
    "convnext_v2_tiny_eu-common256px": {
        "hf_repo": "birder-project/convnext_v2_tiny_eu-common",
        "pt": "convnext_v2_tiny_eu-common256px.pt",
        "meta": "convnext_v2_tiny_eu-common256px.json",
    },
    "convnext_v2_tiny_eu-common": {
        "hf_repo": "birder-project/convnext_v2_tiny_eu-common",
        "pt": "convnext_v2_tiny_eu-common.pt",
        "meta": "convnext_v2_tiny_eu-common.json",
    },
    "rope_vit_reg4_b14_capi-intermediate-eu-common": {
        "hf_repo": "birder-project/rope_vit_reg4_b14_capi-intermediate-eu-common",
        "pt": "rope_vit_reg4_b14_capi-intermediate-eu-common.pt",
        "meta": "rope_vit_reg4_b14_capi-intermediate-eu-common.json",
    },
}

DEFAULT_VARIANT = "convnext_v2_tiny_eu-common256px"


def download_variant(variant: str, classification_root: Path) -> Path:
    from huggingface_hub import hf_hub_download

    spec = MODELS[variant]
    classification_root.mkdir(parents=True, exist_ok=True)
    model_dir = classification_root / variant
    model_dir.mkdir(parents=True, exist_ok=True)

    for key in ("pt", "meta"):
        fname = spec[key]
        cached = hf_hub_download(repo_id=spec["hf_repo"], filename=fname)
        dest = model_dir / fname
        shutil.copy2(cached, dest)

    import birder

    net, info, _ = birder.load_pretrained_model_and_transform(variant, inference=True)
    del net
    idx2label = {int(v): str(k) for k, v in info.class_to_idx.items()}
    lines = [idx2label[i] for i in range(len(idx2label))]
    (model_dir / "class_labels.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "model_id": spec["hf_repo"],
        "variant": variant,
        "num_labels": len(idx2label),
        "input_size": int(info.signature["inputs"][0]["data_shape"][-1]),
        "rgb_stats": info.rgb_stats,
        "architecture": variant,
    }
    (model_dir / "birdlense_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK {model_dir}/ labels={len(idx2label)}")
    jays = [n for n in lines if "jay" in n.lower()]
    print("jay classes:", jays)
    return model_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default=DEFAULT_VARIANT, choices=sorted(MODELS))
    parser.add_argument(
        "--dest",
        type=Path,
        default=REPO / "app" / "processor" / "models" / "classification",
        help="Classification root (default: app/processor/models/classification)",
    )
    parser.add_argument(
        "--export-onnx",
        action="store_true",
        help="After download, run scripts/export_birder_classifier_to_onnx.py",
    )
    args = parser.parse_args()
    download_variant(args.variant, args.dest)
    if args.export_onnx:
        export_script = REPO / "scripts" / "export_birder_classifier_to_onnx.py"
        subprocess.run(
            [sys.executable, str(export_script), "--variant", args.variant, "--dest", str(args.dest)],
            check=True,
        )


if __name__ == "__main__":
    main()
