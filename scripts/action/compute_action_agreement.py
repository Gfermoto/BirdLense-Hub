#!/usr/bin/env python3
# flake8: noqa
"""Compute inter-annotator agreement (Cohen's kappa) for action labels."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        obj = json.loads(ln)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _extract_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        sid = str(row.get("segment_uid") or "").strip()
        lbl = str(row.get("action_label") or row.get("label") or "").strip()
        if not sid or not lbl:
            continue
        out[sid] = lbl
    return out


def _compute_kappa(labels_a: list[str], labels_b: list[str]) -> tuple[float, dict[str, Any]]:
    if len(labels_a) != len(labels_b):
        raise ValueError("labels_a and labels_b must have equal length")
    n = len(labels_a)
    if n == 0:
        raise ValueError("no overlapping rows for agreement")

    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    po = float(agree) / float(n)

    ca = Counter(labels_a)
    cb = Counter(labels_b)
    label_set = sorted(set(ca.keys()) | set(cb.keys()))
    pe = 0.0
    for l in label_set:
        pe += (float(ca[l]) / float(n)) * (float(cb[l]) / float(n))
    if abs(1.0 - pe) < 1e-12:
        kappa = 1.0 if abs(po - 1.0) < 1e-12 else 0.0
    else:
        kappa = (po - pe) / (1.0 - pe)

    confusion: dict[str, dict[str, int]] = {la: defaultdict(int) for la in label_set}
    for a, b in zip(labels_a, labels_b):
        confusion[a][b] += 1
    confusion_plain = {k: dict(v) for k, v in confusion.items()}

    return kappa, {
        "n": n,
        "agreement": agree,
        "po": po,
        "pe": pe,
        "labels": label_set,
        "counts_annotator_a": dict(ca),
        "counts_annotator_b": dict(cb),
        "confusion": confusion_plain,
    }


def compute_report(
    *,
    annotator_a_jsonl: Path,
    annotator_b_jsonl: Path,
    min_kappa: float | None,
    max_disagreements: int,
) -> tuple[bool, dict[str, Any]]:
    rows_a = _read_jsonl(annotator_a_jsonl)
    rows_b = _read_jsonl(annotator_b_jsonl)
    map_a = _extract_map(rows_a)
    map_b = _extract_map(rows_b)

    keys_a = set(map_a.keys())
    keys_b = set(map_b.keys())
    overlap = sorted(keys_a & keys_b)
    only_a = sorted(keys_a - keys_b)
    only_b = sorted(keys_b - keys_a)

    labels_a = [map_a[k] for k in overlap]
    labels_b = [map_b[k] for k in overlap]
    kappa, meta = _compute_kappa(labels_a, labels_b)

    disagreements = []
    for sid in overlap:
        la = map_a[sid]
        lb = map_b[sid]
        if la != lb:
            disagreements.append(
                {
                    "segment_uid": sid,
                    "annotator_a_label": la,
                    "annotator_b_label": lb,
                }
            )
            if len(disagreements) >= int(max_disagreements):
                break

    ok = True
    reasons: list[str] = []
    if min_kappa is not None and kappa < float(min_kappa):
        ok = False
        reasons.append(f"kappa_below_threshold:{kappa:.6f}<{float(min_kappa):.6f}")

    report = {
        "schema": "action_agreement_report@v1",
        "ok": ok,
        "kappa": float(kappa),
        "min_kappa": float(min_kappa) if min_kappa is not None else None,
        "meta": meta,
        "coverage": {
            "overlap_count": len(overlap),
            "only_in_annotator_a": len(only_a),
            "only_in_annotator_b": len(only_b),
        },
        "samples": {
            "only_in_annotator_a": only_a[:10],
            "only_in_annotator_b": only_b[:10],
            "disagreements": disagreements,
        },
        "reasons": reasons,
    }
    return ok, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotator-a-jsonl", required=True)
    parser.add_argument("--annotator-b-jsonl", required=True)
    parser.add_argument("--min-kappa", type=float, default=None)
    parser.add_argument("--max-disagreements", type=int, default=50)
    parser.add_argument("--output-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok, report = compute_report(
        annotator_a_jsonl=Path(args.annotator_a_jsonl).resolve(),
        annotator_b_jsonl=Path(args.annotator_b_jsonl).resolve(),
        min_kappa=float(args.min_kappa) if args.min_kappa is not None else None,
        max_disagreements=int(args.max_disagreements),
    )
    if args.output_json:
        out = Path(args.output_json).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
