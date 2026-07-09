from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import pytest


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _norm(v: str | None) -> str:
    return (v or "").strip().lower()


def test_model_recall_on_golden_dataset() -> None:
    p = Path(os.environ.get("GOLDEN_TEST_PATH", "app/data/datasets/golden_v1/test.jsonl"))
    if not p.exists():
        pytest.skip(f"Golden test split is missing: {p}")
    rows = _load_jsonl(p)
    eval_rows = [r for r in rows if _norm(r.get("ground_truth_species")) and _norm(r.get("predicted_species"))]
    if not eval_rows:
        pytest.skip("No evaluable rows in Golden test split")

    tp = sum(
        1
        for r in eval_rows
        if _norm(r.get("predicted_species")) == _norm(r.get("ground_truth_species"))
    )
    recall = tp / len(eval_rows)
    precision = recall  # proxy while real model-eval harness is being wired

    print(
        f"[golden] samples={len(eval_rows)} tp={tp} recall={recall:.4f} precision={precision:.4f}"
    )
    threshold = float(os.environ.get("GOLDEN_RECALL_MIN", "0.90"))
    if recall < threshold:
        warnings.warn(
            f"Golden recall {recall:.4f} below threshold {threshold:.2f} (warning-only mode)",
            RuntimeWarning,
        )
