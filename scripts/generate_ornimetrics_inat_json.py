#!/usr/bin/env python3
"""Build species_classifier_inat.json for Ornimetrics ONNX (302 classes).

HF publishes species_classifier_inat.onnx but not the matching .json sidecar.
Ornimetrics documents 302 CC iNaturalist NA species; class order is training-specific
and is NOT inferable from the ONNX graph alone.

Usage:
  python3 scripts/generate_ornimetrics_inat_json.py \
    --classes-file path/to/inat_302_classes.txt \
    --output app/processor/models/classification/ornimetrics/species_classifier_inat.json

Template stats (input_size, rgb_mean, rgb_std) are copied from species_classifier_nabirds.json
on Hugging Face — same Ornimetrics backbone head layout as the NABirds pack.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ORNIMETRICS_NABIRDS_JSON = (
    "https://huggingface.co/Ornimetrics/ornimetrics-edge/resolve/main/"
    "models/species_classifier_nabirds.json"
)
EXPECTED_CLASSES = 302


def _load_nabirds_template() -> dict:
    with urllib.request.urlopen(ORNIMETRICS_NABIRDS_JSON, timeout=120) as resp:
        tpl = json.load(resp)
    for key in ("input_size", "rgb_mean", "rgb_std"):
        if key not in tpl:
            raise SystemExit(f"NABirds template missing key: {key}")
    return tpl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--classes-file", type=Path, required=True)
    ap.add_argument(
        "--output",
        type=Path,
        default=Path(
            "app/processor/models/classification/ornimetrics/species_classifier_inat.json"
        ),
    )
    args = ap.parse_args()
    lines = [
        ln.strip()
        for ln in args.classes_file.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if len(lines) != EXPECTED_CLASSES:
        raise SystemExit(
            f"Expected {EXPECTED_CLASSES} class labels, got {len(lines)} in {args.classes_file}"
        )
    tpl = _load_nabirds_template()
    out = {
        "input_size": int(tpl["input_size"]),
        "rgb_mean": tpl["rgb_mean"],
        "rgb_std": tpl["rgb_std"],
        "classes": lines,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
