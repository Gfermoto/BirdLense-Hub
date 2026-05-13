#!/usr/bin/env python3
"""Train multinomial logistic baseline on manifest meta-features (#416 Wave 2).

Requires: pip install scikit-learn
Inputs: behavior_dataset_manifest@v1 (see ``make ml-build-behavior-dataset``).
Outputs:
  - behavior_logistic_export@v1.json — weights for ``processor.behavior_recognition.weights_path``
  - predictions JSON for ``make ml-build-behavior-train-report``
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from sklearn.linear_model import LogisticRegression
except ImportError as e:  # pragma: no cover - optional dependency
    raise SystemExit("Install scikit-learn: pip install scikit-learn") from e

EXPORT_SCHEMA = "behavior_logistic_export@v1"


def _meta_features(row: dict[str, Any]) -> list[float]:
    frame_rows = float(row.get("frame_rows") or 0)
    subject_count = float(row.get("subject_count") or 0)
    species = row.get("species_names") or []
    nsp = float(len(species)) if isinstance(species, list) else 0.0
    return [
        math.log1p(max(0.0, frame_rows)),
        subject_count / 20.0,
        nsp / 10.0,
    ]


def _dominant_behavior_id(row: dict[str, Any]) -> int | None:
    raw = row.get("behavior_counts") or {}
    if not isinstance(raw, dict) or not raw:
        return None
    best_id: int | None = None
    best_n = -1
    for k, v in raw.items():
        try:
            bid = int(k)
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > best_n:
            best_n = n
            best_id = bid
    return best_id


def train_and_export(
    manifest: dict[str, Any],
    *,
    max_iter: int = 500,
    seed: int = 42,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if str(manifest.get("schema") or "") != "behavior_dataset_manifest@v1":
        raise ValueError("manifest schema must be behavior_dataset_manifest@v1")
    tax = manifest.get("taxonomy") or []
    id_to_label: dict[int, str] = {}
    for row in tax:
        if not isinstance(row, dict):
            continue
        try:
            bid = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        lab = str(row.get("label") or "").strip().lower()
        if lab:
            id_to_label[bid] = lab
    if not id_to_label:
        raise ValueError("empty taxonomy labels")

    X_list: list[list[float]] = []
    y_list: list[str] = []
    for row in manifest.get("videos") or []:
        if not isinstance(row, dict):
            continue
        dom_id = _dominant_behavior_id(row)
        if dom_id is None or dom_id not in id_to_label:
            continue
        y_list.append(id_to_label[dom_id])
        X_list.append(_meta_features(row))

    if len(X_list) < 4:
        raise ValueError(f"need at least 4 training rows, got {len(X_list)}")

    import numpy as np

    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list)

    clf = LogisticRegression(
        max_iter=int(max_iter),
        random_state=int(seed),
        solver="lbfgs",
    )
    clf.fit(X, y)

    classes = [str(c) for c in clf.classes_]
    n_features = int(X.shape[1])
    raw_coef = np.asarray(clf.coef_, dtype=np.float64)
    raw_inter = np.asarray(clf.intercept_, dtype=np.float64).reshape(-1)
    if len(classes) == 2:
        # sklearn OvR: shape (1, F); positive class is classes_[1]. Export two logits for softmax
        # so runtime (n_classes, n_features) matches len(labels).
        w = raw_coef.reshape(-1)
        b = float(raw_inter[0]) if raw_inter.size else 0.0
        coef = [[0.0] * n_features, w.tolist()]
        intercept = [0.0, b]
    else:
        coef = raw_coef.tolist()
        intercept = raw_inter.tolist()

    export = {
        "schema": EXPORT_SCHEMA,
        "feature_mode": "manifest_meta_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "labels": classes,
        "coef": coef,
        "intercept": intercept,
        "manifest_dataset_id": manifest.get("dataset_id"),
    }

    pred_rows: list[dict[str, Any]] = []
    for row in manifest.get("videos") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("video_key") or "").strip()
        if not key:
            continue
        xf = np.array([_meta_features(row)], dtype=np.float64)
        proba = clf.predict_proba(xf)[0]
        idx = int(np.argmax(proba))
        pred_rows.append(
            {
                "video_key": key,
                "pred_label": classes[idx],
                "confidence": round(float(proba[idx]), 6),
            }
        )

    predictions = {"schema": "behavior_predictions@v1", "predictions": pred_rows}
    return export, predictions


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--export-out", required=True)
    p.add_argument("--predictions-out", required=True)
    p.add_argument("--max-iter", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    export, predictions = train_and_export(manifest, max_iter=args.max_iter, seed=args.seed)
    Path(args.export_out).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    Path(args.export_out).expanduser().resolve().write_text(
        json.dumps(export, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path(args.predictions_out).expanduser().resolve().write_text(
        json.dumps(predictions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"ok": True, "export": str(Path(args.export_out).resolve()), "n_rows": len(predictions["predictions"])},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
