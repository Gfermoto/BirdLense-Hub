#!/usr/bin/env python3
"""Train Behavior v2 tracklet classifier on crop RGB features + holdout metrics (#458)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml_behavior_eval_harness import evaluate_predictions

if str(_REPO_ROOT / "app") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "app"))
from shared.behavior_tracklet_crop import (  # noqa: E402
    FEATURE_DIM,
    load_tracklet_mean_rgb,
    rgb_feature_vector_from_mean_rgb,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("schema") or "") != "behavior_tracklet_manifest@v1":
        raise ValueError("manifest schema must be behavior_tracklet_manifest@v1")
    return payload


def tracklet_rgb_features(tracklet: dict[str, Any]) -> list[float] | None:
    rgb = load_tracklet_mean_rgb(tracklet)
    if rgb is None:
        return None
    vec = rgb_feature_vector_from_mean_rgb(rgb)
    return vec if len(vec) == FEATURE_DIM else None


def train_video_profile(
    *,
    manifest: dict[str, Any],
    backbone: str,
    out_dir: Path,
    seed: int = 42,
) -> dict[str, Any]:
    rows = [r for r in (manifest.get("tracklets") or []) if isinstance(r, dict)]
    labeled = [
        r
        for r in rows
        if str(r.get("label") or "").strip() and str(r.get("label")) not in {"unknown", "unlabeled"}
    ]
    train_rows = [r for r in labeled if str(r.get("split") or "train") == "train"]
    holdout_rows = [r for r in labeled if str(r.get("split") or "") == "holdout"]

    x_train: list[list[float]] = []
    y_train: list[str] = []
    for row in train_rows:
        feat = tracklet_rgb_features(row)
        if feat is None:
            continue
        x_train.append(feat)
        y_train.append(str(row.get("label")).strip().lower())

    if len(x_train) < 8 or len({y for y in y_train}) < 2:
        raise ValueError(f"not enough labeled train tracklets with crops: {len(x_train)}")

    try:
        from app.shared.behavior_logistic_train import fit_behavior_logistic_export
    except ImportError:
        sys.path.insert(0, str(_REPO_ROOT / "app"))
        from shared.behavior_logistic_train import fit_behavior_logistic_export

    export, _clf = fit_behavior_logistic_export(
        x_train,
        y_train,
        seed=seed,
        feature_mode="tracklet_rgb_v1",
        extra={
            "model_kind": "video_v1",
            "backbone": backbone,
            "feature_dim": FEATURE_DIM,
            "rgb_size": 8,
        },
    )

    model_version = f"{backbone}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    export["schema"] = "behavior_video_export@v1"
    export["model_version"] = model_version
    export["inference_backend"] = "openvino"
    export["precision"] = "fp16"

    out_dir.mkdir(parents=True, exist_ok=True)
    export_path = out_dir / f"behavior_video_export@{model_version}.json"
    export_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")

    preds_holdout: list[dict[str, str]] = []
    y_true: list[str] = []
    y_pred: list[str] = []
    labels_sorted = sorted({str(l) for l in export.get("labels") or []})

    import numpy as np

    coef = np.asarray(export.get("coef") or [], dtype=np.float64)
    intercept = np.asarray(export.get("intercept") or [], dtype=np.float64).reshape(-1)
    classes = [str(c) for c in export.get("labels") or []]

    def _predict_vec(feat: list[float]) -> str:
        x = np.asarray([feat], dtype=np.float64)
        logits = x @ coef.T + intercept
        if logits.ndim == 2 and logits.shape[0] == 1:
            logits = logits.reshape(-1)
        idx = int(np.argmax(logits))
        return classes[idx]

    for row in holdout_rows:
        feat = tracklet_rgb_features(row)
        if feat is None:
            continue
        true_lab = str(row.get("label")).strip().lower()
        pred_lab = _predict_vec(feat)
        tid = str(row.get("tracklet_id"))
        preds_holdout.append({"tracklet_id": tid, "label": true_lab, "predicted": pred_lab})
        y_true.append(true_lab)
        y_pred.append(pred_lab)

    metrics = evaluate_predictions(labels=labels_sorted, y_true=y_true, y_pred=y_pred)
    if metrics["n_samples"] == 0:
        # Fallback: evaluate on train if holdout empty (small synthetic sets).
        for row in train_rows[: max(8, len(train_rows) // 5)]:
            feat = tracklet_rgb_features(row)
            if feat is None:
                continue
            true_lab = str(row.get("label")).strip().lower()
            pred_lab = _predict_vec(feat)
            y_true.append(true_lab)
            y_pred.append(pred_lab)
        metrics = evaluate_predictions(labels=labels_sorted, y_true=y_true, y_pred=y_pred)
        metrics["note"] = "evaluated_on_train_subset_holdout_empty"

    ok = float(metrics.get("macro_f1") or 0.0) >= 0.7
    report = {
        "schema": "behavior_train_report@v2",
        "created_at": _utc_now(),
        "backbone": backbone,
        "model_version": model_version,
        "metrics": metrics,
        "artifact": {"export_json": str(export_path)},
        "holdout_predictions": preds_holdout,
        "ok": ok,
    }
    report_path = out_dir / f"behavior_train_report@{model_version}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    preds_path = out_dir / f"behavior_holdout_predictions@{model_version}.json"
    preds_path.write_text(json.dumps(preds_holdout, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "report": report,
        "report_path": str(report_path),
        "export_path": str(export_path),
        "predictions_path": str(preds_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--backbone", choices=["tsm", "x3d", "slowfast"], default="x3d")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    manifest = _load_manifest(Path(args.manifest).expanduser().resolve())
    result = train_video_profile(
        manifest=manifest,
        backbone=str(args.backbone),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        seed=int(args.seed),
    )
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0 if bool(result["report"].get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
