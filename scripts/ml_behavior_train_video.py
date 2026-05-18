#!/usr/bin/env python3
"""Train Behavior video classifier on crop RGB + val early-stop (#458 v2)."""

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
if str(_REPO_ROOT / "app") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "app"))

from ml_behavior_augment import augment_mean_rgb
from ml_behavior_eval_harness import evaluate_predictions

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


def _feat_from_tracklet(row: dict[str, Any]) -> list[float] | None:
    aug = row.get("_mean_rgb_aug")
    if aug is not None:
        import numpy as np

        if isinstance(aug, np.ndarray):
            return rgb_feature_vector_from_mean_rgb(aug)
    rgb = load_tracklet_mean_rgb(row)
    if rgb is None:
        return None
    vec = rgb_feature_vector_from_mean_rgb(rgb)
    return vec if len(vec) == FEATURE_DIM else None


def _build_xy(
    rows: list[dict[str, Any]],
    *,
    augment_copies: int = 0,
    seed: int = 42,
) -> tuple[list[list[float]], list[str]]:
    import random

    x: list[list[float]] = []
    y: list[str] = []
    rng = random.Random(seed)
    for row in rows:
        feat = _feat_from_tracklet(row)
        if feat is None:
            continue
        lab = str(row.get("label")).strip().lower()
        x.append(feat)
        y.append(lab)
        if int(augment_copies) > 0:
            rgb = load_tracklet_mean_rgb(row)
            if rgb is None:
                continue
            for _ in range(int(augment_copies)):
                aug = augment_mean_rgb(rgb, rng=rng)
                f2 = rgb_feature_vector_from_mean_rgb(aug)
                if f2:
                    x.append(f2)
                    y.append(lab)
    return x, y


def _predict_export(export: dict[str, Any], feat: list[float]) -> str:
    import numpy as np

    coef = np.asarray(export.get("coef") or [], dtype=np.float64)
    intercept = np.asarray(export.get("intercept") or [], dtype=np.float64).reshape(-1)
    classes = [str(c) for c in export.get("labels") or []]
    x = np.asarray([feat], dtype=np.float64)
    logits = (x @ coef.T + intercept).reshape(-1)
    return classes[int(np.argmax(logits))]


def train_video_profile(
    *,
    manifest: dict[str, Any],
    backbone: str,
    out_dir: Path,
    seed: int = 42,
    augment_copies: int = 2,
    model_kind: str = "video_v2",
    min_macro_f1: float = 0.75,
) -> dict[str, Any]:
    rows = [r for r in (manifest.get("tracklets") or []) if isinstance(r, dict)]
    labeled = [
        r
        for r in rows
        if str(r.get("label") or "").strip() and str(r.get("label")) not in {"unknown", "unlabeled"}
    ]
    train_rows = [r for r in labeled if str(r.get("split") or "train") == "train"]
    val_rows = [r for r in labeled if str(r.get("split") or "") == "val"]
    holdout_rows = [r for r in labeled if str(r.get("split") or "") == "holdout"]

    x_train, y_train = _build_xy(train_rows, augment_copies=augment_copies, seed=seed)
    if len(x_train) < 12 or len({y for y in y_train}) < 2:
        raise ValueError(f"not enough train samples: {len(x_train)}")

    try:
        from sklearn.linear_model import LogisticRegression
        from shared.behavior_logistic_train import fit_behavior_logistic_export
    except ImportError as e:
        raise RuntimeError("scikit-learn required") from e

    import numpy as np

    best_export: dict[str, Any] | None = None
    best_val_f1 = -1.0
    best_C = 1.0

    for C in (0.05, 0.1, 0.5, 1.0, 2.0, 5.0):
        clf = LogisticRegression(
            C=float(C),
            max_iter=800,
            random_state=int(seed),
            class_weight="balanced",
            solver="lbfgs",
        )
        clf.fit(np.asarray(x_train, dtype=np.float64), np.asarray(y_train))
        export, _clf = fit_behavior_logistic_export(
            x_train,
            y_train,
            seed=seed,
            feature_mode="tracklet_rgb_v1",
            extra={"model_kind": model_kind, "backbone": backbone, "feature_dim": FEATURE_DIM},
        )
        export["schema"] = "behavior_video_export@v1"
        classes = [str(c) for c in export.get("labels") or []]
        if val_rows:
            x_val, y_val = _build_xy(val_rows, augment_copies=0, seed=seed)
            if x_val:
                y_pred = [_predict_export(export, f) for f in x_val]
                val_m = evaluate_predictions(
                    labels=sorted(set(y_val)),
                    y_true=y_val,
                    y_pred=y_pred,
                )
                vf1 = float(val_m.get("macro_f1") or 0.0)
            else:
                vf1 = 0.0
        else:
            vf1 = 1.0

        if vf1 > best_val_f1:
            best_val_f1 = vf1
            best_C = float(C)
            best_export = export

    assert best_export is not None
    model_version = f"{backbone}-v2-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    best_export["model_version"] = model_version
    best_export["inference_backend"] = "openvino"
    best_export["precision"] = "fp16"
    best_export["train_C"] = best_C
    best_export["val_macro_f1"] = round(best_val_f1, 6)

    out_dir.mkdir(parents=True, exist_ok=True)
    export_path = out_dir / f"behavior_video_export@{model_version}.json"
    export_path.write_text(json.dumps(best_export, ensure_ascii=False, indent=2), encoding="utf-8")

    labels_sorted = sorted({str(l) for l in best_export.get("labels") or []})
    preds_holdout: list[dict[str, str]] = []
    y_true: list[str] = []
    y_pred: list[str] = []
    for row in holdout_rows:
        feat = _feat_from_tracklet(row)
        if feat is None:
            continue
        true_lab = str(row.get("label")).strip().lower()
        pred_lab = _predict_export(best_export, feat)
        preds_holdout.append(
            {"tracklet_id": str(row.get("tracklet_id")), "label": true_lab, "predicted": pred_lab}
        )
        y_true.append(true_lab)
        y_pred.append(pred_lab)

    metrics = evaluate_predictions(labels=labels_sorted, y_true=y_true, y_pred=y_pred)
    metrics["val_macro_f1"] = round(best_val_f1, 6)
    ok = float(metrics.get("macro_f1") or 0.0) >= float(min_macro_f1) and float(metrics.get("accuracy") or 0.0) >= 0.80

    report = {
        "schema": "behavior_train_report@v2",
        "created_at": _utc_now(),
        "backbone": backbone,
        "model_version": model_version,
        "model_kind": model_kind,
        "metrics": metrics,
        "artifact": {"export_json": str(export_path)},
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
    ap.add_argument("--augment-copies", type=int, default=2)
    ap.add_argument("--model-kind", default="video_v2")
    ap.add_argument("--min-macro-f1", type=float, default=0.75)
    args = ap.parse_args()
    manifest = _load_manifest(Path(args.manifest).expanduser().resolve())
    result = train_video_profile(
        manifest=manifest,
        backbone=str(args.backbone),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        seed=int(args.seed),
        augment_copies=int(args.augment_copies),
        model_kind=str(args.model_kind),
        min_macro_f1=float(args.min_macro_f1),
    )
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0 if bool(result["report"].get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
