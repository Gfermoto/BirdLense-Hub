"""Live YOLO blind detection: gauges, quickcheck probe, session phase helpers (SOTA-05 / #496)."""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping

logger = logging.getLogger(__name__)

YOLO_BLIND_STATUS_HEALTHY = "healthy"
YOLO_BLIND_STATUS_DEGRADED = "degraded"
YOLO_BLIND_STATUS_BLIND = "blind"


def _cfg_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _cfg_int(cfg: Mapping[str, Any], key: str, default: int) -> int:
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def blind_quickcheck_overrides(cfg: Mapping[str, Any]) -> dict[str, float | int]:
    """Temporary detector overrides for blind quickcheck probe."""
    return {
        "min_confidence_binary": _cfg_float(
            cfg,
            "detection.yolo_blind_quickcheck_min_confidence_binary",
            0.05,
        ),
        "min_confidence_binary_bird": _cfg_float(
            cfg,
            "detection.yolo_blind_quickcheck_min_confidence_binary_bird",
            0.03,
        ),
        "min_box_size_px": _cfg_int(
            cfg,
            "detection.yolo_blind_quickcheck_min_box_size_px",
            10,
        ),
    }


def run_blind_quickcheck(
    frame_processor: Any,
    frame: Any,
    *,
    cfg: Mapping[str, Any],
    frame_time: float | None = None,
    classification_frame: Any = None,
) -> dict[str, Any]:
    """
    Re-run detector with relaxed thresholds (does not mutate session counters).

    Returns ``frame_processor.last_run_stats`` copy after probe.
    """
    overrides = blind_quickcheck_overrides(cfg)
    try:
        frame_processor.run(
            frame,
            frame_time=frame_time,
            skip_light_gate=True,
            classification_frame=classification_frame,
            camera_overrides=overrides,
        )
    except Exception as exc:
        logger.warning("blind quickcheck probe failed: %s", exc)
        return {"yolo_ran": False, "yolo_raw_boxes": 0, "yolo_track_found": False}
    return dict(getattr(frame_processor, "last_run_stats", {}) or {})


class YoloBlindLiveMonitor:
    """
    Tracks Frigate-only activity without YOLO tracks for live ``yolo_blind_alert`` gauge.

    Alert when Frigate extends session (or holds activity) while session has zero
    ``yolo_frames_with_tracks`` for longer than ``alert_seconds``.
    """

    def __init__(self, *, alert_seconds: float = 30.0) -> None:
        self.alert_seconds = max(5.0, float(alert_seconds))
        self._frigate_only_since: float | None = None
        self._last_yolo_track_monotonic: float | None = None

    def on_frame(
        self,
        *,
        frigate_only_extension: bool,
        yolo_track_found: bool,
        yolo_raw_boxes: int,
        runtime_signals: dict[str, Any],
    ) -> None:
        now = time.monotonic()
        if yolo_track_found or yolo_raw_boxes > 0:
            self._last_yolo_track_monotonic = now
            self._frigate_only_since = None
            self._publish_gauges(
                alert=0,
                status=YOLO_BLIND_STATUS_HEALTHY,
                phase=str(runtime_signals.get("yolo_blind_phase") or "none"),
                runtime_signals=runtime_signals,
            )
            return

        if frigate_only_extension:
            if self._frigate_only_since is None:
                self._frigate_only_since = now
            elapsed = now - self._frigate_only_since
            alert = 1 if elapsed >= self.alert_seconds else 0
            status = YOLO_BLIND_STATUS_BLIND if alert else YOLO_BLIND_STATUS_DEGRADED
            self._publish_gauges(
                alert=alert,
                status=status,
                phase=str(runtime_signals.get("yolo_blind_phase") or "none"),
                runtime_signals=runtime_signals,
                frigate_only_seconds=round(elapsed, 2),
            )
            return

        self._frigate_only_since = None
        phase = str(runtime_signals.get("yolo_blind_phase") or "none")
        if phase in ("suspected", "confirmed"):
            self._publish_gauges(
                alert=1 if phase == "confirmed" else 0,
                status=YOLO_BLIND_STATUS_BLIND if phase == "confirmed" else YOLO_BLIND_STATUS_DEGRADED,
                phase=phase,
                runtime_signals=runtime_signals,
            )
        else:
            self._publish_gauges(
                alert=0,
                status=YOLO_BLIND_STATUS_HEALTHY,
                phase=phase,
                runtime_signals=runtime_signals,
            )

    def _publish_gauges(
        self,
        *,
        alert: int,
        status: str,
        phase: str,
        runtime_signals: dict[str, Any],
        frigate_only_seconds: float | None = None,
    ) -> None:
        try:
            from processor_runtime_stats import set_gauge

            set_gauge("yolo_blind_alert", int(alert))
            set_gauge("yolo_blind_status", status)
            set_gauge("yolo_blind_phase_live", phase)
            set_gauge("yolo_frames_with_tracks_session", int(runtime_signals.get("yolo_frames_with_tracks") or 0))
            set_gauge(
                "session_extended_by_frigate_only_session",
                int(runtime_signals.get("session_extended_by_frigate_only") or 0),
            )
            if frigate_only_seconds is not None:
                set_gauge("yolo_blind_frigate_only_seconds", float(frigate_only_seconds))
        except Exception:
            logger.debug("yolo_blind gauge publish failed", exc_info=True)


def evaluate_detector_health_from_snapshot(
    gauges: Mapping[str, Any],
    *,
    recent_blind_confirmed: bool = False,
    recent_blind_score: float = 0.0,
    blind_score_threshold: float = 0.7,
) -> dict[str, Any]:
    """Map runtime gauges + DB hints to UI status payload."""
    status = str(gauges.get("yolo_blind_status") or YOLO_BLIND_STATUS_HEALTHY)
    alert = int(gauges.get("yolo_blind_alert") or 0)
    phase = str(gauges.get("yolo_blind_phase_live") or gauges.get("last_yolo_blind_phase") or "none")

    reasons: list[str] = []
    if recent_blind_confirmed or alert == 1 or status == YOLO_BLIND_STATUS_BLIND:
        status = YOLO_BLIND_STATUS_BLIND
        reasons.append("live_alert_or_confirmed_blind")
    elif status == YOLO_BLIND_STATUS_DEGRADED or phase == "suspected":
        status = YOLO_BLIND_STATUS_DEGRADED
        reasons.append("blind_suspected_or_frigate_only_without_yolo")
    if recent_blind_score >= blind_score_threshold:
        reasons.append(f"session_blind_score>={blind_score_threshold}")

    return {
        "status": status,
        "yolo_blind_alert": bool(alert),
        "yolo_blind_phase": phase,
        "yolo_frames_with_tracks_session": int(gauges.get("yolo_frames_with_tracks_session") or 0),
        "session_extended_by_frigate_only": int(gauges.get("session_extended_by_frigate_only_session") or 0),
        "stream_probe_width": gauges.get("stream_probe_width"),
        "stream_probe_height": gauges.get("stream_probe_height"),
        "stream_probe_fps": gauges.get("stream_probe_fps"),
        "reasons": reasons,
    }
