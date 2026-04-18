"""Одна сессия записи по движению: выбор камеры, цикл кадров, финализация (#225 / #238)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from argparse import Namespace

from app_config.app_config import app_config
from app_config.trigger_config import format_trigger_display_line, get_active_trigger_names
from birdnet_mqtt_confidence import merge_birdnet_mqtt_bias_into_overrides
from fps_tracker import FPSTracker
from processor_support import get_output_path, processor_status
from recording_finalize import finalize_motion_recording

logger = logging.getLogger(__name__)


class MotionRecordingSession:
    """Явные зависимости одного цикла «motion → запись → finalize» (тонкий orchestrator в main)."""

    def __init__(
        self,
        *,
        args: Namespace,
        api: Any,
        motion_detector: Any,
        mqtt_aggregator: Any,
        frame_processor: Any,
        decision_maker: Any,
        merged_overrides: dict,
        media_source_ref: list,
        get_media_source: Callable[..., Any],
        default_camera_id: str,
        scales_topic_arg: Optional[str],
        data_dir: str,
        fps_tracker: FPSTracker,
        file_test_runtime: Any = None,
    ) -> None:
        self.args = args
        self.api = api
        self.motion_detector = motion_detector
        self.mqtt_aggregator = mqtt_aggregator
        self.frame_processor = frame_processor
        self.decision_maker = decision_maker
        self.merged_overrides = merged_overrides
        self._media_source_ref = media_source_ref
        self.get_media_source = get_media_source
        self.default_camera_id = default_camera_id
        self.scales_topic_arg = scales_topic_arg
        self.data_dir = data_dir
        self.fps_tracker = fps_tracker
        self.file_test_runtime = file_test_runtime

    @property
    def media_source(self) -> Any:
        return self._media_source_ref[0]

    @media_source.setter
    def media_source(self, value: Any) -> None:
        self._media_source_ref[0] = value

    def _session_activity_camera_ids(self, camera_id: str | None) -> list[str]:
        cameras: list[str] = []
        if camera_id:
            cameras.append(str(camera_id))
        groups = app_config.get("processor.multi_camera_groups") or []
        for group in groups:
            if not isinstance(group, (list, tuple, set)):
                continue
            normalized = [str(item).strip() for item in group if str(item).strip()]
            if camera_id and str(camera_id) in normalized:
                cameras.extend(normalized)
        return sorted(set(cameras))

    def _has_session_activity(
        self,
        *,
        has_detections: bool,
        camera_id: str | None,
        frigate_hold_seconds: float,
    ) -> bool:
        if has_detections:
            return True
        if frigate_hold_seconds <= 0:
            return False

        recent_frigate = getattr(self.motion_detector, "has_recent_frigate_activity", None)
        if recent_frigate is None:
            recent_frigate = getattr(self.motion_detector, "has_recent_activity", None)
        if callable(recent_frigate):
            try:
                if bool(
                    recent_frigate(
                        camera=camera_id,
                        max_age_seconds=frigate_hold_seconds,
                    )
                ):
                    return True
            except Exception:
                pass

        aggregator_recent = getattr(self.mqtt_aggregator, "has_recent_frigate_activity", None)
        if callable(aggregator_recent):
            camera_ids = self._session_activity_camera_ids(camera_id)
            if not camera_ids and getattr(self, "default_camera_id", None):
                camera_ids = [str(self.default_camera_id)]
            if not camera_ids:
                return False
            try:
                return bool(
                    aggregator_recent(
                        camera_ids=camera_ids,
                        max_age_seconds=frigate_hold_seconds,
                        min_confidence=0.0,
                    )
                )
            except Exception:
                return False
        return False

    def run(self) -> bool:
        """Выполнить одну запись. Возвращает True, если внешний цикл main должен завершиться (режим --input)."""
        session_overrides = merge_birdnet_mqtt_bias_into_overrides(
            self.merged_overrides, app_config, self.mqtt_aggregator
        )
        self.decision_maker.species_confidence_overrides = session_overrides

        camera_id = getattr(self.motion_detector, "get_triggered_camera", lambda: None)() or self.default_camera_id
        if not self.args.input and app_config.get("video.source") == "go2rtc":
            self.media_source = self.get_media_source(camera_id)

        output_path_physical, output_path_logical = get_output_path()
        video_output = os.path.join(output_path_physical, "video.mp4")
        video_path_for_api = f"{output_path_logical}/video.mp4"

        self.media_source.start_recording(video_output)

        logger.info(
            'Motion detected. Processing started. Recording video and audio to "%s"',
            video_output,
        )
        start_time = datetime.now(timezone.utc)

        try:
            self.frame_processor.reset()
            self.decision_maker.reset()
            self.fps_tracker.reset()
            file_mode = (app_config.get("video.source") or "").strip().lower() == "file"
            try:
                frigate_hold_seconds = float(app_config.get("processor.frigate_activity_hold_seconds") or 0.0)
            except (TypeError, ValueError):
                frigate_hold_seconds = 0.0
            runtime_signals = {
                "frames_seen": 0,
                "yolo_frames_ran": 0,
                "yolo_frames_with_tracks": 0,
                "low_light_blocked_frames": 0,
                "session_extended_by_frigate_only": 0,
            }
            frame_n = 0
            while True:
                if self.file_test_runtime and self.file_test_runtime.abort_session:
                    logger.info("File test: stop requested, ending session")
                    break
                frame = self.media_source.capture()
                if frame is None:
                    break
                frame_n += 1
                runtime_signals["frames_seen"] += 1
                if self.file_test_runtime:
                    self.file_test_runtime.poll_during_active_session()
                if file_mode and frame_n % 500 == 0:
                    clip = getattr(self.media_source, "video_path", "") or ""
                    clip_name = Path(str(clip)).name if clip else "?"
                    logger.info(
                        "video.source=file: processing clip=%s frames_in_session=%s",
                        clip_name,
                        frame_n,
                    )
                processor_status["last_video_ok_at"] = datetime.now(timezone.utc).isoformat()
                frame_time = getattr(self.media_source, "get_frame_time", lambda: None)()
                with self.fps_tracker:
                    has_detections = self.frame_processor.run(frame, frame_time=frame_time)
                run_stats = dict(getattr(self.frame_processor, "last_run_stats", {}) or {})
                if run_stats.get("yolo_ran"):
                    runtime_signals["yolo_frames_ran"] += 1
                    processor_status["last_yolo_ok_at"] = datetime.now(timezone.utc).isoformat()
                if run_stats.get("yolo_track_found"):
                    runtime_signals["yolo_frames_with_tracks"] += 1
                    processor_status["last_yolo_detection_at"] = datetime.now(timezone.utc).isoformat()
                if run_stats.get("light_gate_blocked"):
                    runtime_signals["low_light_blocked_frames"] += 1

                raw_yolo_detections = bool(has_detections)
                has_detections = self._has_session_activity(
                    has_detections=has_detections,
                    camera_id=camera_id,
                    frigate_hold_seconds=frigate_hold_seconds,
                )
                if has_detections and not raw_yolo_detections:
                    runtime_signals["session_extended_by_frigate_only"] += 1

                self.decision_maker.update_has_detections(has_detections)
                self.decision_maker.get_first_species_result(
                    self.frame_processor.tracks,
                )
                if self.decision_maker.decide_stop_recording():
                    break
            self.fps_tracker.log_summary()
        finally:
            if self.file_test_runtime:
                self.file_test_runtime.poll()
                self.file_test_runtime.abort_session = False
            self.media_source.stop_recording()
            end_time = datetime.now(timezone.utc)

        try:
            _mqtt_b = (os.environ.get("MQTT_BROKER") or app_config.get("mqtt.broker") or "").strip() or None
            _active_names = get_active_trigger_names(app_config, mqtt_broker=_mqtt_b)
            finalize_motion_recording(
                self.api,
                self.motion_detector,
                self.mqtt_aggregator,
                self.frame_processor,
                self.decision_maker,
                start_time=start_time,
                end_time=end_time,
                output_path_physical=output_path_physical,
                output_path_logical=output_path_logical,
                video_output=video_output,
                video_path_for_api=video_path_for_api,
                scales_topic_arg=self.scales_topic_arg,
                data_dir=self.data_dir,
                recording_context={
                    "triggered_camera": camera_id,
                    "frigate_activity_hold_seconds": frigate_hold_seconds,
                    "triggered_by": getattr(self.motion_detector, "get_triggered_by", lambda: None)(),
                    "trigger_display": format_trigger_display_line(_active_names),
                    "pipeline_policy": dict(getattr(self.frame_processor, "pipeline_policy", {}) or {}),
                    "runtime_signals": {
                        **runtime_signals,
                        "yolo_ran": runtime_signals["yolo_frames_ran"] > 0,
                        "yolo_track_found": runtime_signals["yolo_frames_with_tracks"] > 0,
                        "session_extended_by_frigate": runtime_signals["session_extended_by_frigate_only"] > 0,
                    },
                },
            )
        except Exception as e:
            logger.error(e)

        return bool(self.args.input)
