#!/usr/bin/env python3
"""Export behavior_video_export@v1 to ONNX + OpenVINO IR FP16 (#458)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _video_export_to_logistic(export: dict) -> dict:
    if str(export.get("schema") or "") != "behavior_video_export@v1":
        raise ValueError("expected behavior_video_export@v1")
    if not export.get("coef") or not export.get("intercept") or not export.get("labels"):
        raise ValueError("video export missing coef/intercept/labels (train first)")
    return {
        "schema": "behavior_logistic_export@v1",
        "labels": export["labels"],
        "coef": export["coef"],
        "intercept": export["intercept"],
        "feature_mode": export.get("feature_mode") or "tracklet_rgb_v1",
    }


def export_video_openvino(
    *,
    video_export_path: Path,
    out_dir: Path,
    precision: str = "fp16",
    model_basename: str = "behavior_video_model",
) -> dict:
    export = json.loads(video_export_path.read_text(encoding="utf-8"))
    logistic = _video_export_to_logistic(export)

    from ml_behavior_export_onnx import export_behavior_logistic_onnx

    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / f"{model_basename}.onnx"
    export_behavior_logistic_onnx(export_json=logistic, out_onnx=onnx_path)

    xml_path = out_dir / f"{model_basename}.xml"
    bin_path = out_dir / f"{model_basename}.bin"

    try:
        import openvino as ov
    except ImportError as e:
        raise RuntimeError("openvino required for IR export") from e

    compress = precision == "fp16"
    try:
        ov_model = ov.convert_model(str(onnx_path), compress_to_fp16=compress)
    except TypeError:
        ov_model = ov.convert_model(str(onnx_path))
    try:
        ov.save_model(ov_model, str(xml_path), compress_to_fp16=compress)
    except TypeError:
        ov.save_model(ov_model, str(out_dir / model_basename))

    if not xml_path.is_file():
        # Some OV versions write model.xml under a directory basename.
        alt = out_dir / model_basename / f"{model_basename}.xml"
        if alt.is_file():
            xml_path = alt
            bin_path = alt.with_suffix(".bin")
    if not xml_path.is_file() or not bin_path.is_file():
        raise RuntimeError(f"OpenVINO IR not created under {out_dir}")

    descriptor = {
        "schema": "behavior_openvino_export@v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_version": export.get("model_version"),
        "model_kind": export.get("model_kind") or "video_v1",
        "precision": precision,
        "source_export": str(video_export_path.resolve()),
        "files": {
            "xml": str(xml_path.resolve()),
            "bin": str(bin_path.resolve()),
            "onnx": str(onnx_path.resolve()),
        },
        "labels": export.get("labels") or [],
        "feature_dim": export.get("feature_dim"),
    }
    desc_path = out_dir / "behavior_openvino_export.json"
    desc_path.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"descriptor": str(desc_path), "xml": str(xml_path), "bin": str(bin_path)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video-export", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--precision", choices=["fp16", "fp32"], default="fp16")
    ap.add_argument("--model-basename", default="behavior_video_model")
    args = ap.parse_args()
    rep = export_video_openvino(
        video_export_path=Path(args.video_export).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        precision=str(args.precision),
        model_basename=str(args.model_basename),
    )
    print(json.dumps({"ok": True, **rep}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
