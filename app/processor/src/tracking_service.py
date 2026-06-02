"""Shared video tracking loop for Live parity and Regen (SOTA-11)."""

from __future__ import annotations

import logging
import math
import os
import time
from typing import Any, Callable

import cv2

from frame_geometry import prepare_detector_pipeline_frame
from tracking_policy import (
    UnifiedTrackingPolicy,
    attach_tracking_policy_to_strategy,
    build_unified_tracking_policy,
)

logger = logging.getLogger(__name__)


class TrackingService:
    """YOLO + ByteTrack over a video file with unified policy."""

    def __init__(
        self,
        frame_processor: Any,
        decision_maker: Any,
        policy: UnifiedTrackingPolicy,
        *,
        runtime_cfg: dict | None = None,
    ) -> None:
        self.frame_processor = frame_processor
        self.decision_maker = decision_maker
        self.policy = policy
        self.runtime_cfg = runtime_cfg

    @classmethod
    def from_regen_pipeline(
        cls,
        frame_processor: Any,
        decision_maker: Any,
        *,
        runtime_cfg: dict | None = None,
        source_fps: float = 0.0,
        frame_step: int = 1,
    ) -> TrackingService:
        from app_config.app_config import app_config

        cfg = runtime_cfg or app_config.config or {}
        policy = build_unified_tracking_policy(
            cfg,
            mode="regen",
            source_fps=source_fps,
            frame_step=frame_step,
        )
        frame_processor.set_session_context(policy.session_context())
        frame_processor.tracking_policy = policy
        attach_tracking_policy_to_strategy(frame_processor.strategy, policy)
        return cls(frame_processor, decision_maker, policy, runtime_cfg=cfg)

    def process_video(
        self,
        video_path: str,
        *,
        frame_step: int | None = None,
        max_runtime_sec: int | None = None,
        progress_hook: Callable[[dict[str, Any]], None] | None = None,
        progress_hook_interval: int = 20,
        metrics_out: dict[str, Any] | None = None,
        infer_lock: Any | None = None,
    ) -> list[dict]:
        if not os.path.isfile(video_path):
            logger.warning("Video not found: %s", video_path)
            return []

        step = max(1, int(frame_step if frame_step is not None else self.policy.frame_step))
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("Cannot open video: %s", video_path)
            return []

        fps = float(self.policy.source_fps or 0.0)
        if fps <= 0.5:
            raw_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if raw_fps > 0.5:
                fps = raw_fps
        if fps <= 0.5:
            from pipeline_config import resolve_stream_fps
            from app_config.app_config import app_config

            fps = float(resolve_stream_fps(None, app_config))

        self.policy.source_fps = fps
        self.policy.frame_step = step
        self.frame_processor.set_session_context(self.policy.session_context())

        geom_mode = self.policy.geometry_mode_for_frame()
        frame_total_guess = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        try:
            fcg = float(frame_total_guess)
            yolo_runs_est = int(math.ceil(fcg / float(step))) if fcg > 1.5 else None
        except (TypeError, ValueError):
            yolo_runs_est = None
        if yolo_runs_est is not None:
            yolo_runs_est = max(1, yolo_runs_est)

        frame_count = 0
        runs_done = 0
        if metrics_out is not None:
            metrics_out.clear()
            metrics_out.update(
                {
                    "total_frames": 0,
                    "yolo_frames_ran": 0,
                    "yolo_raw_boxes_total": 0,
                    "yolo_accepted_boxes_total": 0,
                    "yolo_boxes_with_track_id_total": 0,
                    "frames_with_tracks": 0,
                    "processing_seconds": 0.0,
                    "tracking_unified_with_live": bool(self.policy.unified_with_live),
                    "tracking_geometry_mode": geom_mode,
                }
            )

        _hi = max(1, int(progress_hook_interval or 20))
        started = time.monotonic()
        cfg = self.runtime_cfg
        if cfg is None:
            from app_config.app_config import app_config

            cfg = app_config.config or {}

        try:
            while True:
                if max_runtime_sec and (time.monotonic() - started) > max_runtime_sec:
                    raise TimeoutError(f"Tracking timeout ({max_runtime_sec}s) for {video_path}")
                if frame_count % step == 0:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_time_sec = frame_count / fps if fps > 0.5 else float(frame_count)
                    frame_resized, _, _, _ = prepare_detector_pipeline_frame(
                        frame,
                        cfg,
                        mode=geom_mode,
                    )

                    def _run_once() -> bool:
                        return self.frame_processor.run(
                            frame_resized,
                            frame_time=frame_time_sec,
                            skip_light_gate=self.policy.skip_light_gate,
                            classification_frame=frame,
                        )

                    if infer_lock is not None:
                        with infer_lock:
                            has_detections = _run_once()
                    else:
                        has_detections = _run_once()

                    self.decision_maker.update_has_detections(has_detections)
                    runs_done += 1
                    self._accumulate_metrics(metrics_out)
                    if progress_hook and (
                        runs_done == 1
                        or runs_done % _hi == 0
                        or (yolo_runs_est is not None and runs_done >= yolo_runs_est)
                    ):
                        try:
                            progress_hook(
                                {
                                    "phase": "yolo_infer",
                                    "yolo_frames_done": runs_done,
                                    "yolo_frames_total": yolo_runs_est,
                                }
                            )
                        except Exception:
                            logger.debug("progress_hook failed", exc_info=True)
                else:
                    if not cap.grab():
                        break
                frame_count += 1
        finally:
            cap.release()
            if metrics_out is not None:
                metrics_out["total_frames"] = int(frame_count)
                metrics_out["processing_seconds"] = round(max(0.0, time.monotonic() - started), 4)
                if metrics_out["processing_seconds"] > 0 and metrics_out.get("yolo_frames_ran"):
                    metrics_out["processing_fps"] = round(
                        float(metrics_out["yolo_frames_ran"]) / float(metrics_out["processing_seconds"]),
                        3,
                    )
                else:
                    metrics_out["processing_fps"] = 0.0

        return self.frame_processor.tracks

    def _accumulate_metrics(self, metrics_out: dict[str, Any] | None) -> None:
        if metrics_out is None:
            return
        run_stats = getattr(self.frame_processor, "last_run_stats", None) or {}
        metrics_out["yolo_frames_ran"] = int(metrics_out.get("yolo_frames_ran") or 0) + 1
        metrics_out["yolo_raw_boxes_total"] = int(metrics_out.get("yolo_raw_boxes_total") or 0) + int(
            run_stats.get("yolo_raw_boxes") or 0
        )
        metrics_out["yolo_accepted_boxes_total"] = int(metrics_out.get("yolo_accepted_boxes_total") or 0) + int(
            run_stats.get("yolo_accepted_boxes") or 0
        )
        metrics_out["yolo_boxes_with_track_id_total"] = int(
            metrics_out.get("yolo_boxes_with_track_id_total") or 0
        ) + int(run_stats.get("yolo_boxes_with_track_id") or 0)
        if bool(run_stats.get("yolo_track_found")):
            metrics_out["frames_with_tracks"] = int(metrics_out.get("frames_with_tracks") or 0) + 1
