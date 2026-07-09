#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROC_SRC = ROOT / "app" / "processor" / "src"
if str(PROC_SRC) not in sys.path:
    sys.path.insert(0, str(PROC_SRC))

from roi_super_resolution import build_roi_super_resolution  # noqa: E402


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return float(self.tp) / float(d) if d else 0.0

    @property
    def fpr(self) -> float:
        d = self.fp + self.tn
        return float(self.fp) / float(d) if d else 0.0


def _make_crop(rng: random.Random, *, positive: bool, size: int) -> np.ndarray:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    noise = rng.randint(10, 25)
    img[:] = rng.randint(35, 90)
    n = rng.randint(3, 6)
    for _ in range(n):
        x = rng.randint(0, size - 1)
        y = rng.randint(0, size - 1)
        cv2.circle(img, (x, y), rng.randint(1, 2), (rng.randint(20, 50),) * 3, -1)
    if positive:
        cx = rng.randint(max(3, size // 4), min(size - 4, (3 * size) // 4))
        cy = rng.randint(max(3, size // 4), min(size - 4, (3 * size) // 4))
        rw = rng.randint(2, 4)
        rh = rng.randint(2, 4)
        cv2.ellipse(img, (cx, cy), (rw, rh), rng.uniform(-20, 20), 0, 360, (160, 160, 160), -1)
        cv2.circle(img, (min(size - 1, cx + rw), max(0, cy - 1)), 1, (200, 200, 200), -1)
    img = cv2.GaussianBlur(img, (3, 3), sigmaX=1.0)
    alpha = rng.uniform(0.55, 0.85)
    beta = rng.uniform(-14, 6)
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    grain = np.random.normal(0, noise, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + grain, 0, 255).astype(np.uint8)
    return img


def _bird_score(crop: np.ndarray) -> float:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), sigmaX=0.8)
    hp = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    p99 = float(np.percentile(np.abs(hp), 99))
    return p99


def _predict_positive(crop: np.ndarray, *, threshold: float) -> bool:
    return _bird_score(crop) >= threshold


def _choose_threshold(samples: list[tuple[np.ndarray, bool]]) -> float:
    scored = [(_bird_score(img), label) for img, label in samples]
    vals = [s for s, _ in scored]
    if not vals:
        return 10.0
    candidates = np.percentile(vals, np.linspace(45, 95, 40))
    best_thr = float(candidates[0])
    best_bacc = -1.0
    for thr in candidates:
        c = Counts()
        for score, label in scored:
            pred = score >= float(thr)
            if pred and label:
                c.tp += 1
            elif pred and not label:
                c.fp += 1
            elif (not pred) and label:
                c.fn += 1
            else:
                c.tn += 1
        tpr = c.recall
        tnr = 1.0 - c.fpr
        bacc = 0.5 * (tpr + tnr)
        if bacc > best_bacc:
            best_bacc = bacc
            best_thr = float(thr)
    return best_thr


def _evaluate(samples: list[tuple[np.ndarray, bool]], *, threshold: float) -> Counts:
    c = Counts()
    for img, label in samples:
        pred = _predict_positive(img, threshold=threshold)
        if pred and label:
            c.tp += 1
        elif pred and not label:
            c.fp += 1
        elif (not pred) and label:
            c.fn += 1
        else:
            c.tn += 1
    return c


def run(model: str, samples: list[tuple[np.ndarray, bool]]) -> dict:
    cfg = {
        "experimental.sr_enabled": True,
        "experimental.sr_model": model,
        "experimental.sr_scale": 2,
        "experimental.sr_min_crop_px": 10,
        "experimental.sr_max_crop_px": 96,
        "experimental.sr_max_latency_ms": 50,
    }
    sr = build_roi_super_resolution(cfg)
    baseline_threshold = _choose_threshold(samples)
    baseline = _evaluate(samples, threshold=baseline_threshold)

    sr_samples: list[tuple[np.ndarray, bool]] = []
    lat_ms: list[float] = []
    native_count = 0
    for img, label in samples:
        t0 = time.perf_counter()
        up, meta = sr.enhance(img)
        lat_ms.append((time.perf_counter() - t0) * 1000.0)
        if meta.native:
            native_count += 1
        sr_samples.append((up, label))
    sr_counts = _evaluate(sr_samples, threshold=baseline_threshold)

    recall_gain = sr_counts.recall - baseline.recall
    fpr_delta = sr_counts.fpr - baseline.fpr
    return {
        "model": model,
        "native_model_loaded": bool(native_count > 0),
        "baseline": {
            "recall": round(baseline.recall, 4),
            "fpr": round(baseline.fpr, 4),
            "tp": baseline.tp,
            "fp": baseline.fp,
            "fn": baseline.fn,
            "tn": baseline.tn,
        },
        "sr": {
            "recall": round(sr_counts.recall, 4),
            "fpr": round(sr_counts.fpr, 4),
            "tp": sr_counts.tp,
            "fp": sr_counts.fp,
            "fn": sr_counts.fn,
            "tn": sr_counts.tn,
        },
        "recall_gain": round(recall_gain, 4),
        "fpr_delta": round(fpr_delta, 4),
        "latency_overhead_ms_p50": round(float(np.percentile(lat_ms, 50)), 3),
        "latency_overhead_ms_p95": round(float(np.percentile(lat_ms, 95)), 3),
        "baseline_threshold": round(float(baseline_threshold), 4),
    }


def _render_report(results: list[dict], samples_n: int) -> str:
    best = sorted(results, key=lambda x: (x["recall_gain"], -x["latency_overhead_ms_p95"]), reverse=True)[0]
    go = best["recall_gain"] > 0.05 and best["latency_overhead_ms_p95"] < 20.0
    verdict = "GO" if go else "NO-GO"
    lines = [
        "# ROI Super-Resolution Pilot",
        "",
        f"- Samples: **{samples_n}** synthetic low-contrast crops (balanced labels).",
        "- Models: **fsrcnn_x2**, **realesrgan_x2**.",
        "",
        "| model | native loaded | recall baseline | recall sr | recall gain | fpr delta | p95 overhead (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['model']} | {str(r['native_model_loaded']).lower()} | "
            f"{r['baseline']['recall']:.4f} | {r['sr']['recall']:.4f} | {r['recall_gain']:.4f} | "
            f"{r['fpr_delta']:.4f} | {r['latency_overhead_ms_p95']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            f"- Best candidate: **{best['model']}**",
            f"- Rule: recall gain > 0.05 and p95 overhead < 20ms",
            f"- Verdict: **{verdict}**",
            "",
            "## Suggested production config",
            "```yaml",
            "experimental:",
            f"  sr_enabled: {'true' if go else 'false'}",
            f"  sr_model: \"{best['model']}\"",
            "  sr_scale: 2",
            "  sr_min_crop_px: 10",
            "  sr_max_crop_px: 96",
            "  sr_max_latency_ms: 20",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="ROI SR pilot benchmark (#472)")
    ap.add_argument("--samples", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--out-md",
        type=Path,
        default=ROOT / "docs" / "benchmarks" / "sr_roi_pilot.md",
    )
    ap.add_argument(
        "--out-json",
        type=Path,
        default=ROOT / "docs" / "benchmarks" / "sr_roi_pilot.json",
    )
    args = ap.parse_args()

    rng = random.Random(args.seed)
    samples: list[tuple[np.ndarray, bool]] = []
    pos = args.samples // 2
    neg = args.samples - pos
    for _ in range(pos):
        samples.append((_make_crop(rng, positive=True, size=rng.randint(16, 44)), True))
    for _ in range(neg):
        samples.append((_make_crop(rng, positive=False, size=rng.randint(16, 44)), False))
    rng.shuffle(samples)

    results = [run("fsrcnn_x2", samples), run("realesrgan_x2", samples)]
    report = _render_report(results, args.samples)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(report, encoding="utf-8")
    args.out_json.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {args.out_md}")
    print(f"saved: {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
