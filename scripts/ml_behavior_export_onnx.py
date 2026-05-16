#!/usr/bin/env python3
"""Export behavior_logistic_export@v1.json to ONNX for OpenVINO Runtime (#416 Wave 4).

Single Gemm: logits = X @ W.T + b (X shape [1, n_features]).

Requires: pip install onnx (не обязательно в образе процессора — OpenVINO читает .onnx напрямую).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def export_behavior_logistic_onnx(*, export_json: dict, out_onnx: Path) -> None:
    try:
        import numpy as np
        from onnx import TensorProto, helper
        from onnx import numpy_helper
    except ImportError as e:
        raise RuntimeError(
            "Экспорт ONNX требует пакеты onnx и numpy: pip install onnx",
        ) from e

    if str(export_json.get("schema") or "") != "behavior_logistic_export@v1":
        raise ValueError("schema must be behavior_logistic_export@v1")
    coef = export_json.get("coef") or []
    intercept = export_json.get("intercept") or []
    labels = export_json.get("labels") or []
    if not coef or not intercept or not labels:
        raise ValueError("coef, intercept and labels required")

    w = np.asarray(coef, dtype=np.float32)
    if w.ndim != 2:
        raise ValueError(f"coef must be 2-dim, got shape {w.shape}")
    n_classes, n_feat = int(w.shape[0]), int(w.shape[1])
    b = np.asarray(intercept, dtype=np.float32).reshape(-1)
    if b.shape[0] != n_classes:
        raise ValueError(f"intercept length {b.shape[0]} != n_classes {n_classes}")

    # Gemm: Y = X @ B + C with X [1, n_feat], B = W.T [n_feat, n_classes]
    bt = w.T.astype(np.float32)
    bias = b.astype(np.float32)

    x_info = helper.make_tensor_value_info("X", TensorProto.FLOAT, [1, n_feat])
    logits_info = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, n_classes])

    init_w = numpy_helper.from_array(bt, name="W")
    init_b = numpy_helper.from_array(bias, name="B")

    gemm = helper.make_node(
        "Gemm",
        inputs=["X", "W", "B"],
        outputs=["logits"],
        alpha=1.0,
        beta=1.0,
        transA=0,
        transB=0,
    )
    graph = helper.make_graph(
        [gemm],
        "behavior_logistic",
        [x_info],
        [logits_info],
        initializer=[init_w, init_b],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    try:
        import onnx

        onnx.checker.check_model(model)
    except Exception:
        pass

    out_onnx.parent.mkdir(parents=True, exist_ok=True)
    Path(out_onnx).write_bytes(model.SerializeToString())


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--export-json", required=True, help="behavior_logistic_export@v1.json")
    p.add_argument("--out-onnx", required=True)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    payload = json.loads(Path(args.export_json).read_text(encoding="utf-8"))
    outp = Path(args.out_onnx).expanduser().resolve()
    export_behavior_logistic_onnx(export_json=payload, out_onnx=outp)
    print(json.dumps({"ok": True, "out_onnx": str(outp)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
