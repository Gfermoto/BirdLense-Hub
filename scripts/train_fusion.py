#!/usr/bin/env python3
"""Train a small fusion scorer (MLP) on CSV features.

Usage example:
  python3 scripts/train_fusion.py --data features.csv --out-dir app/processor/models/fusion --epochs 5

If CSV is missing, a tiny synthetic dataset is generated so the script runs on CPU
for demonstration.
"""
from __future__ import annotations

import argparse
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Tuple

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH = True
except Exception:
    TORCH = False

try:
    import numpy as np
except Exception:
    np = None

import csv
import random

FEATURE_COLS = [
    "detector_conf",
    "classifier_conf",
    "birdnet_prior",
    "key_frame_score",
    "key_frame_count",
    "multi_camera_count",
]
LABEL_COLS = [
    "valid_track_label",
    "species_top1_label",
    "label",
]


def load_csv(path: Path) -> Tuple[list, list]:
    X = []
    y = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        label_col = next(
            (col for col in LABEL_COLS if reader.fieldnames and col in reader.fieldnames),
            "label",
        )
        for r in reader:
            x = [float(r.get(c, 0.0) or 0.0) for c in FEATURE_COLS]
            X.append(x)
            y.append(int(float(r.get(label_col, 0) or 0)))
    return X, y


def synth_data(n: int = 200):
    X = []
    y = []
    rnd = random.Random(42)
    for i in range(n):
        classifier = rnd.random() * 0.9 + 0.05
        detector = rnd.random() * 0.9 + 0.05
        birdnet = rnd.random() * 0.5
        key_score = rnd.random()
        key_count = rnd.randint(0, 3)
        multi = rnd.randint(0, 2)
        label = 1 if (classifier > 0.6 and detector > 0.3) or (birdnet > 0.4) else 0
        X.append([detector, classifier, birdnet, key_score, key_count, multi])
        y.append(label)
    return X, y


def save_metadata(out_dir: Path, metrics: dict, model_name: str, extra: dict = None):
    meta = {
        "model_name": model_name,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "metrics": metrics,
    }
    if extra:
        meta.update(extra)
    out = out_dir / "metadata.json"
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("Wrote metadata:", out)


def train_torch(X, y, device: str, epochs: int, out_dir: Path):
    import torch.utils.data as data
    Xt = torch.tensor(X, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.float32)
    ds = data.TensorDataset(Xt, yt)
    dl = data.DataLoader(ds, batch_size=32, shuffle=True)

    model = nn.Sequential(
        nn.Linear(len(FEATURE_COLS), 32),
        nn.ReLU(),
        nn.Linear(32, 16),
        nn.ReLU(),
        nn.Linear(16, 1),
    )
    model.to(device)
    opt = optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    model.train()
    for ep in range(epochs):
        total = 0.0
        for xb, yb in dl:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            logits = model(xb).squeeze(-1)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            total += float(loss.item()) * xb.size(0)
        print(f"epoch {ep+1}/{epochs} loss={total/len(ds):.4f}")
    # save
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "fusion_state.pt"
    torch.save(model.state_dict(), model_path)
    print("Saved model:", model_path)
    # compute simple accuracy on train
    model.eval()
    with torch.no_grad():
        logits = model(Xt.to(device)).squeeze(-1)
        probs = torch.sigmoid(logits).cpu().numpy()
        preds = (probs > 0.5).astype(int)
    import numpy as np
    acc = float((preds == np.array(y)).mean())
    save_metadata(out_dir, {"train_acc": acc}, model_name=str(model_path))


def train_sklearn(X, y, out_dir: Path):
    try:
        from sklearn.linear_model import LogisticRegression  # type: ignore
    except Exception:
        train_fallback(X, y, out_dir)
        return

    if np is None:
        train_fallback(X, y, out_dir)
        return

    Xn = np.array(X)
    yn = np.array(y)
    clf = LogisticRegression(max_iter=200)
    clf.fit(Xn, yn)
    out_dir.mkdir(parents=True, exist_ok=True)
    # save sklearn model as pickle
    import pickle

    p = out_dir / "fusion_state.pkl"
    with p.open("wb") as f:
        pickle.dump(clf, f)
    preds = clf.predict(Xn)
    acc = float((preds == yn).mean())
    save_metadata(out_dir, {"train_acc": acc}, model_name=str(p))
    print("Saved sklearn model:", p)


def train_fallback(X, y, out_dir: Path):
    """Save a simple heuristic calibration snapshot when ML deps are missing."""
    out_dir.mkdir(parents=True, exist_ok=True)
    positives = [row for row, label in zip(X, y) if label]
    negatives = [row for row, label in zip(X, y) if not label]
    weights = [0.15, 0.5, 0.15, 0.1, 0.05, 0.05]
    if positives and negatives:
        pos_mean = [sum(col) / len(col) for col in zip(*positives)]
        neg_mean = [sum(col) / len(col) for col in zip(*negatives)]
        weights = [max(-1.0, min(1.0, p - n)) for p, n in zip(pos_mean, neg_mean)]
    payload = {
        "feature_columns": FEATURE_COLS,
        "weights": weights,
        "note": "fallback metadata only; runtime uses deterministic scorer",
    }
    path = out_dir / "fusion_state.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    save_metadata(out_dir, {"fallback_rows": len(X)}, model_name=str(path))
    print("Saved fallback calibration snapshot:", path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data", "-d", type=Path, help="CSV with features (see exporter)")
    p.add_argument("--out-dir", "-o", type=Path, default=Path("app/processor/models/fusion"), help="Output model dir")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--device", type=str, default="cpu")
    args = p.parse_args(argv)

    if args.data and args.data.exists():
        X, y = load_csv(args.data)
    else:
        print("No CSV provided or not found — generating tiny synthetic dataset for demo.")
        X, y = synth_data(200)

    if TORCH:
        device = args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
        train_torch(X, y, device, epochs=args.epochs, out_dir=args.out_dir)
        model_file = args.out_dir / "fusion_state.pt"
        print("Checksum:", sha256_file(model_file))
    else:
        print("PyTorch not available — using sklearn fallback (CPU).")
        train_sklearn(X, y, args.out_dir)

    print("Done.")


if __name__ == "__main__":
    main()

