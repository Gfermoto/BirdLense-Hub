#!/usr/bin/env python3
"""Download Birder EU-common classifier weights (HF birder-project/*) into processor weights."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Primary (quality) and fallback (latency) — see issue #516
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


def _out_dir(variant: str, base: Path) -> Path:
    return base / f"birder_{variant.replace('-', '_')}"


def download_variant(variant: str, base: Path) -> Path:
    from huggingface_hub import hf_hub_download

    spec = MODELS[variant]
    out = _out_dir(variant, base)
    out.mkdir(parents=True, exist_ok=True)

    for key in ("pt", "meta"):
        fname = spec[key]
        cached = hf_hub_download(repo_id=spec["hf_repo"], filename=fname)
        dest = out / fname
        shutil.copy2(cached, dest)

    # Labels for BirdLense catalog / mapping (707 EU species, Collins taxonomy).
    import birder

    net, info, _ = birder.load_pretrained_model_and_transform(variant, inference=True)
    del net
    idx2label = {int(v): str(k) for k, v in info.class_to_idx.items()}
    labels_path = out / "class_labels.txt"
    lines = [idx2label[i] for i in range(len(idx2label))]
    labels_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "model_id": spec["hf_repo"],
        "variant": variant,
        "num_labels": len(idx2label),
        "input_size": int(info.signature["inputs"][0]["data_shape"][-1]),
        "rgb_stats": info.rgb_stats,
        "architecture": variant,
    }
    (out / "birdlense_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK {out} labels={len(idx2label)} input={manifest['input_size']}")
    jays = [n for n in lines if "jay" in n.lower()]
    print("jay classes:", jays)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--variant",
        choices=sorted(MODELS),
        default=DEFAULT_VARIANT,
        help=f"Model variant (default: {DEFAULT_VARIANT})",
    )
    ap.add_argument(
        "--out-base",
        type=Path,
        default=REPO / "app/processor/models/classification/weights",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Download all known EU variants",
    )
    args = ap.parse_args()

    if args.all:
        for v in MODELS:
            download_variant(v, args.out_base)
    else:
        download_variant(args.variant, args.out_base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
