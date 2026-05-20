"""In-process ScoringEngine observability (rolling window, degradation alerts)."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoringTelemetrySnapshot:
    threshold_accept: float
    threshold_reject: float
    calibrated: bool
    calibration_frames: int
    score_histogram_5m: dict[str, int]
    review_share_5m: float
    degradation_alert: bool
    degradation_reason: str | None
    last_decisions: list[dict[str, Any]]
    totals: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold_accept": self.threshold_accept,
            "threshold_reject": self.threshold_reject,
            "calibrated": self.calibrated,
            "calibration_frames": self.calibration_frames,
            "score_histogram_5m": self.score_histogram_5m,
            "review_share_5m": round(self.review_share_5m, 4),
            "degradation_alert": self.degradation_alert,
            "degradation_reason": self.degradation_reason,
            "last_decisions": self.last_decisions,
            "totals": self.totals,
        }


class ScoringTelemetry:
    """Thread-safe rolling metrics for /api/debug/scoring."""

    REVIEW_ALERT_RATIO = 0.20
    WINDOW_SECONDS = 300.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: deque[tuple[float, str]] = deque(maxlen=8000)
        self._recent_decisions: deque[dict[str, Any]] = deque(maxlen=10)
        self._calibration: dict[str, Any] = {}
        self._totals: dict[str, int] = {
            "accept": 0,
            "review": 0,
            "reject": 0,
        }

    def record_calibration(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            self._calibration = dict(snapshot)

    def record_decisions(
        self,
        traces: list[dict[str, Any]],
        *,
        stats: dict[str, int] | None = None,
    ) -> None:
        if not traces:
            return
        now = time.monotonic()
        with self._lock:
            if stats:
                for key in ("scoring_accepted", "scoring_review", "scoring_rejected"):
                    short = key.replace("scoring_", "")
                    n = int(stats.get(key) or 0)
                    if n and short in self._totals:
                        self._totals[short] += n
            for tr in traces:
                zone = str(tr.get("final_decision") or "reject")
                self._events.append((now, zone))
                self._recent_decisions.appendleft(
                    {
                        "frame_index": tr.get("frame_index"),
                        "track_id": tr.get("track_id"),
                        "raw_conf": tr.get("raw_conf"),
                        "final_score": tr.get("final_score"),
                        "final_decision": zone,
                        "reject_reason": tr.get("reject_reason"),
                        "motion_score": tr.get("motion_score"),
                        "shape_score": tr.get("shape_score"),
                        "bg_score": tr.get("bg_score"),
                    }
                )

    def snapshot(self, *, engine_calibration: dict[str, Any] | None = None) -> ScoringTelemetrySnapshot:
        now = time.monotonic()
        cutoff = now - self.WINDOW_SECONDS
        hist = {"accept": 0, "review": 0, "reject": 0}
        with self._lock:
            cal = dict(engine_calibration or self._calibration)
            while self._events and self._events[0][0] < cutoff:
                self._events.popleft()
            for _, zone in self._events:
                if zone in hist:
                    hist[zone] += 1
            total_5m = sum(hist.values())
            review_share = hist["review"] / total_5m if total_5m else 0.0
            alert = review_share > self.REVIEW_ALERT_RATIO and total_5m >= 20
            reason = None
            if alert:
                reason = (
                    f"review_share={review_share:.1%} exceeds {self.REVIEW_ALERT_RATIO:.0%} "
                    "(scene drift — recalibration recommended)"
                )
            last = list(self._recent_decisions)[:10]
            totals = dict(self._totals)
            low = float(cal.get("low_threshold") or 0.38)
            high = float(cal.get("high_threshold") or 0.52)
            return ScoringTelemetrySnapshot(
                threshold_accept=high,
                threshold_reject=low,
                calibrated=bool(cal.get("calibrated")),
                calibration_frames=int(cal.get("frame_count") or 0),
                score_histogram_5m=hist,
                review_share_5m=review_share,
                degradation_alert=alert,
                degradation_reason=reason,
                last_decisions=last,
                totals=totals,
            )


_telemetry: ScoringTelemetry | None = None
_telemetry_lock = threading.Lock()


def get_scoring_telemetry() -> ScoringTelemetry:
    global _telemetry
    with _telemetry_lock:
        if _telemetry is None:
            _telemetry = ScoringTelemetry()
        return _telemetry
