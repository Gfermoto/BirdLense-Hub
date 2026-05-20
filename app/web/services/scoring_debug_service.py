"""Build /api/debug/scoring from decision trace JSONL + config (cross-process safe)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app_config.app_config import app_config

REVIEW_ALERT_RATIO = 0.20
WINDOW = timedelta(minutes=5)


def _repo_data_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def _iter_recent_trace_records(max_files: int = 3, max_lines: int = 500) -> list[dict[str, Any]]:
    root = _repo_data_root() / "decision_traces"
    if not root.is_dir():
        return []
    files = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[:max_files]:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines[-max_lines:]:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") == "session_start":
                continue
            out.append(rec)
    return out


def build_scoring_debug_payload() -> dict[str, Any]:
    proc = app_config.get("processor") or {}
    low = float(proc.get("scoring_default_low_threshold") or 0.38)
    high = float(proc.get("scoring_default_high_threshold") or 0.52)
    records = _iter_recent_trace_records()
    cutoff = datetime.now(timezone.utc) - WINDOW
    hist: Counter[str] = Counter()
    last_decisions: list[dict[str, Any]] = []
    calibrated = False
    for rec in reversed(records):
        ts_raw = rec.get("ts")
        if ts_raw:
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
            except ValueError:
                pass
        zone = str(rec.get("final_decision") or "reject")
        if zone in ("accept", "review", "reject"):
            hist[zone] += 1
        if rec.get("calibrated"):
            calibrated = True
        if "low_threshold" in rec:
            low = float(rec["low_threshold"])
        if "high_threshold" in rec:
            high = float(rec["high_threshold"])
        if len(last_decisions) < 10:
            last_decisions.append(
                {
                    "frame_index": rec.get("frame_index"),
                    "track_id": rec.get("track_id"),
                    "raw_conf": rec.get("raw_conf"),
                    "final_score": rec.get("final_score"),
                    "final_decision": zone,
                    "reject_reason": rec.get("reject_reason"),
                    "motion_score": rec.get("motion_score"),
                    "shape_score": rec.get("shape_score"),
                    "bg_score": rec.get("bg_score"),
                }
            )

    total = sum(hist.values())
    review_share = hist["review"] / total if total else 0.0
    alert = review_share > REVIEW_ALERT_RATIO and total >= 20
    reason = None
    if alert:
        reason = (
            f"review_share={review_share:.1%} exceeds {REVIEW_ALERT_RATIO:.0%} "
            "(scene drift — recalibration recommended)"
        )

    return {
        "threshold_accept": high,
        "threshold_reject": low,
        "calibrated": calibrated,
        "scoring_engine_enabled": bool(proc.get("scoring_engine_enabled")),
        "score_histogram_5m": dict(hist),
        "review_share_5m": round(review_share, 4),
        "degradation_alert": alert,
        "degradation_reason": reason,
        "last_decisions": last_decisions,
        "trace_records_in_window": total,
        "weights": {
            "conf": float(proc.get("scoring_weight_conf") or 0.45),
            "motion": float(proc.get("scoring_weight_motion") or 0.25),
            "shape": float(proc.get("scoring_weight_shape") or 0.15),
            "background": float(proc.get("scoring_weight_background") or 0.15),
        },
    }
