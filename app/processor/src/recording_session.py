"""Одна сессия записи по движению: выбор камеры, цикл кадров, финализация (#225 / #238)."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import Any, Callable, Optional

from argparse import Namespace

from app_config.app_config import app_config
from app_config.trigger_config import format_trigger_display_line, get_active_trigger_names
from birdnet_mqtt_confidence import merge_birdnet_mqtt_bias_into_overrides
from fps_tracker import FPSTracker
from processor_support import get_output_path, processor_status
from processor_runtime_stats import inc_counter, observe_timing, set_gauge
from recording_finalize import finalize_motion_recording
from session_state_repository import SessionStateRepository

logger = logging.getLogger(__name__)


def _camera_processor_overrides(camera_id: str | None) -> dict:
    """Per-camera processor overrides from ``processor.camera_overrides.<camera_id>``."""
    cam = str(camera_id or "").strip()
    if not cam:
        return {}
    raw = app_config.get(f"processor.camera_overrides.{cam}")
    return dict(raw) if isinstance(raw, dict) else {}


def _classifier_use_source_frame() -> bool:
    """Toggle source-frame crops for classifier/ReID (env overrides config)."""
    env_raw = (os.environ.get("BIRDLENSE_CLASSIFIER_USE_SOURCE_FRAME") or "").strip().lower()
    if env_raw:
        return env_raw in ("1", "true", "yes", "on")
    return bool(app_config.get("processor.classifier_use_source_frame", True))


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
        self.session_state_repo = SessionStateRepository()
        self._startup_blind_confirmed = False
        try:
            blind_min_sessions = int(app_config.get("detection.yolo_blind_required_consecutive_sessions") or 1)
            blind_min_frames = int(app_config.get("detection.yolo_blind_min_frames") or 180)
            blind_min_frigate = int(app_config.get("detection.yolo_blind_min_frigate_only_frames") or 120)
            blind_min_duration_s = float(app_config.get("detection.yolo_blind_min_duration_seconds") or 30.0)
            blind_min_effective_fps = float(app_config.get("detection.yolo_blind_min_effective_fps") or 2.0)
            self._startup_blind_confirmed = self.session_state_repo.is_blind_confirmed(
                camera_id=self.default_camera_id,
                min_recent_sessions=max(1, blind_min_sessions),
                min_yolo_frames=max(1, blind_min_frames),
                min_frigate_only_frames=max(1, blind_min_frigate),
                min_duration_seconds=max(0.0, blind_min_duration_s),
                min_effective_fps=max(0.1, blind_min_effective_fps),
            )
            if self._startup_blind_confirmed:
                set_gauge("yolo_blind_restored_state", "1")
                logger.warning(
                    "recording_session: restored blind-state context for camera=%s",
                    self.default_camera_id,
                )
        except Exception:
            logger.debug("recording_session: startup state restore failed", exc_info=True)

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
                logger.debug(
                    "recording_session: motion_detector frigate probe failed camera=%s",
                    camera_id,
                    exc_info=True,
                )

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
                logger.debug(
                    "recording_session: mqtt_aggregator frigate probe failed cameras=%s",
                    camera_ids,
                    exc_info=True,
                )
                return False
        return False

    def run(self) -> bool:
        """Выполнить одну запись. Возвращает True, если внешний цикл main должен завершиться (режим --input)."""
        session_overrides = merge_birdnet_mqtt_bias_into_overrides(
            self.merged_overrides, app_config, self.mqtt_aggregator
        )
        self.decision_maker.species_confidence_overrides = session_overrides

        from motion_recording_camera import resolve_motion_recording_camera_id

        camera_id = resolve_motion_recording_camera_id(
            self.motion_detector,
            mqtt_aggregator=self.mqtt_aggregator,
            default_camera_id=self.default_camera_id,
        )
        frigate_trigger_event = None
        if getattr(self.motion_detector, "get_triggered_by", lambda: None)() == "frigate":
            _last_frigate = getattr(self.motion_detector, "get_last_frigate_event", None)
            if callable(_last_frigate):
                _ev = _last_frigate()
                if isinstance(_ev, dict) and _ev:
                    frigate_trigger_event = {**_ev, "_session_trigger_snapshot": True}
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
            inc_counter("recording_session_total")
            file_mode = (app_config.get("video.source") or "").strip().lower() == "file"
            try:
                frigate_hold_seconds = float(app_config.get("processor.frigate_activity_hold_seconds") or 0.0)
            except (TypeError, ValueError):
                frigate_hold_seconds = 0.0
            try:
                none_frame_retries = int(app_config.get("processor.capture_none_frame_retries") or 3)
            except (TypeError, ValueError):
                none_frame_retries = 3
            try:
                none_frame_retry_sleep_ms = int(app_config.get("processor.capture_none_frame_retry_sleep_ms") or 80)
            except (TypeError, ValueError):
                none_frame_retry_sleep_ms = 80
            none_frame_retries = max(0, none_frame_retries)
            none_frame_retry_sleep_s = max(0.0, float(none_frame_retry_sleep_ms) / 1000.0)
            runtime_signals = {
                "frames_seen": 0,
                "yolo_frames_ran": 0,
                "yolo_frames_with_tracks": 0,
                "yolo_frames_with_raw_boxes": 0,
                "yolo_raw_boxes_total": 0,
                "yolo_accepted_boxes_total": 0,
                "low_light_blocked_frames": 0,
                "session_extended_by_frigate_only": 0,
                "yolo_blind_phase": "none",
                "blind_quickcheck_frames": 0,
                "blind_quickcheck_hits": 0,
            }
            blind_suspected_since_monotonic: float | None = None
            blind_quickcheck_until_monotonic = 0.0
            try:
                blind_min_frames = int(app_config.get("detection.yolo_blind_min_frames") or 180)
            except (TypeError, ValueError):
                blind_min_frames = 180
            try:
                blind_min_frigate = int(app_config.get("detection.yolo_blind_min_frigate_only_frames") or 120)
            except (TypeError, ValueError):
                blind_min_frigate = 120
            try:
                quickcheck_seconds = float(app_config.get("detection.yolo_blind_quickcheck_seconds") or 2.0)
            except (TypeError, ValueError):
                quickcheck_seconds = 2.0
            try:
                quickcheck_min_conf = float(app_config.get("detection.yolo_blind_quickcheck_min_confidence_binary") or 0.05)
            except (TypeError, ValueError):
                quickcheck_min_conf = 0.05
            try:
                quickcheck_min_bird_conf = float(
                    app_config.get("detection.yolo_blind_quickcheck_min_confidence_binary_bird") or 0.03
                )
            except (TypeError, ValueError):
                quickcheck_min_bird_conf = 0.03
            try:
                quickcheck_min_box = int(app_config.get("detection.yolo_blind_quickcheck_min_box_size_px") or 10)
            except (TypeError, ValueError):
                quickcheck_min_box = 10
            runtime_profile_counts: Counter[str] = Counter()
            runtime_profile_overrides: dict[str, dict] = {}
            camera_overrides = _camera_processor_overrides(camera_id)
            if camera_overrides:
                self.decision_maker.apply_runtime_overrides(camera_overrides)

            def _accumulate_run_stats(local_stats: dict) -> int:
                if local_stats.get("yolo_ran"):
                    runtime_signals["yolo_frames_ran"] += 1
                    processor_status["last_yolo_ok_at"] = datetime.now(timezone.utc).isoformat()
                if local_stats.get("yolo_track_found"):
                    runtime_signals["yolo_frames_with_tracks"] += 1
                    processor_status["last_yolo_detection_at"] = datetime.now(timezone.utc).isoformat()
                raw_boxes_local = int(local_stats.get("yolo_raw_boxes") or 0)
                if raw_boxes_local > 0:
                    runtime_signals["yolo_frames_with_raw_boxes"] += 1
                    runtime_signals["yolo_raw_boxes_total"] += raw_boxes_local
                runtime_signals["yolo_accepted_boxes_total"] += int(local_stats.get("yolo_accepted_boxes") or 0)
                if local_stats.get("light_gate_blocked"):
                    runtime_signals["low_light_blocked_frames"] += 1
                return raw_boxes_local
            frame_n = 0
            consecutive_none_frames = 0
            while True:
                if self.file_test_runtime and self.file_test_runtime.abort_session:
                    logger.info("File test: stop requested, ending session")
                    break
                frame = self.media_source.capture()
                if frame is None:
                    if not file_mode and none_frame_retries > 0:
                        consecutive_none_frames += 1
                        inc_counter("recording_capture_none_frame_total")
                        if consecutive_none_frames <= none_frame_retries:
                            logger.warning(
                                "recording_session: capture returned empty frame (%s/%s), retrying",
                                consecutive_none_frames,
                                none_frame_retries,
                            )
                            if none_frame_retry_sleep_s > 0:
                                time.sleep(none_frame_retry_sleep_s)
                            continue
                        inc_counter("recording_capture_none_frame_abort_total")
                        logger.warning(
                            "recording_session: capture returned empty frame %s times подряд; closing session",
                            consecutive_none_frames,
                        )
                    break
                if consecutive_none_frames > 0:
                    inc_counter("recording_capture_none_frame_recovered_total")
                    consecutive_none_frames = 0
                classifier_source_frame = None
                if _classifier_use_source_frame():
                    classifier_source_frame = getattr(
                        self.media_source,
                        "get_classifier_source_frame",
                        lambda: None,
                    )()
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
                    has_detections = self.frame_processor.run(
                        frame,
                        frame_time=frame_time,
                        classification_frame=classifier_source_frame,
                        camera_overrides=camera_overrides,
                    )
                run_stats = dict(getattr(self.frame_processor, "last_run_stats", {}) or {})
                raw_boxes = _accumulate_run_stats(run_stats)
                runtime_profile = str(run_stats.get("runtime_profile") or "").strip()
                if runtime_profile:
                    runtime_profile_counts[runtime_profile] += 1
                    overrides = run_stats.get("profile_overrides") or {}
                    if isinstance(overrides, dict) and overrides:
                        runtime_profile_overrides[runtime_profile] = dict(overrides)

                raw_yolo_detections = bool(has_detections)
                has_detections = self._has_session_activity(
                    has_detections=has_detections,
                    camera_id=camera_id,
                    frigate_hold_seconds=frigate_hold_seconds,
                )
                if has_detections and not raw_yolo_detections:
                    runtime_signals["session_extended_by_frigate_only"] += 1
                    suspicion_ready = (
                        runtime_signals["yolo_frames_ran"] >= max(1, blind_min_frames)
                        and runtime_signals["yolo_raw_boxes_total"] == 0
                        and runtime_signals["session_extended_by_frigate_only"] >= max(1, blind_min_frigate)
                    )
                    if suspicion_ready and runtime_signals["yolo_blind_phase"] == "none":
                        runtime_signals["yolo_blind_phase"] = "suspected"
                        blind_suspected_since_monotonic = time.monotonic()
                        blind_quickcheck_until_monotonic = blind_suspected_since_monotonic + max(0.2, quickcheck_seconds)

                    if runtime_signals["yolo_blind_phase"] == "suspected":
                        now_m = time.monotonic()
                        if now_m <= blind_quickcheck_until_monotonic:
                            burst_overrides = dict(camera_overrides or {})
                            curr_conf = burst_overrides.get(
                                "min_confidence_binary",
                                app_config.get("processor.min_confidence_binary"),
                            )
                            curr_bird_conf = burst_overrides.get(
                                "min_confidence_binary_bird",
                                app_config.get("processor.min_confidence_binary_bird"),
                            )
                            curr_box = burst_overrides.get("min_box_size_px", app_config.get("processor.min_box_size_px"))
                            try:
                                burst_overrides["min_confidence_binary"] = min(float(curr_conf), quickcheck_min_conf)
                            except (TypeError, ValueError):
                                burst_overrides["min_confidence_binary"] = quickcheck_min_conf
                            try:
                                burst_overrides["min_confidence_binary_bird"] = min(
                                    float(curr_bird_conf), quickcheck_min_bird_conf
                                )
                            except (TypeError, ValueError):
                                burst_overrides["min_confidence_binary_bird"] = quickcheck_min_bird_conf
                            try:
                                burst_overrides["min_box_size_px"] = min(int(curr_box), quickcheck_min_box)
                            except (TypeError, ValueError):
                                burst_overrides["min_box_size_px"] = quickcheck_min_box

                            with self.fps_tracker:
                                quick_detect = self.frame_processor.run(
                                    frame,
                                    frame_time=frame_time,
                                    classification_frame=classifier_source_frame,
                                    camera_overrides=burst_overrides,
                                )
                            runtime_signals["blind_quickcheck_frames"] += 1
                            quick_stats = dict(getattr(self.frame_processor, "last_run_stats", {}) or {})
                            quick_raw = _accumulate_run_stats(quick_stats)
                            if quick_detect or quick_raw > 0:
                                runtime_signals["blind_quickcheck_hits"] += 1
                                runtime_signals["yolo_blind_phase"] = "recovered"
                                raw_yolo_detections = True
                                has_detections = True
                                blind_suspected_since_monotonic = None
                        else:
                            runtime_signals["yolo_blind_phase"] = "confirmed"
                elif raw_boxes > 0:
                    runtime_signals["yolo_blind_phase"] = "recovered"
                    blind_suspected_since_monotonic = None

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
            dominant_runtime_profile = None
            dominant_runtime_overrides = {}
            if runtime_profile_counts:
                dominant_runtime_profile = runtime_profile_counts.most_common(1)[0][0]
                dominant_runtime_overrides = dict(runtime_profile_overrides.get(dominant_runtime_profile) or {})
                merged_runtime_overrides = dict(dominant_runtime_overrides)
                merged_runtime_overrides.update(camera_overrides)
                self.decision_maker.apply_runtime_overrides(merged_runtime_overrides)
            session_duration_ms = max(0.0, (end_time - start_time).total_seconds() * 1000.0)
            observe_timing("recording_session_duration", session_duration_ms)
            set_gauge("last_session_frames_seen", runtime_signals["frames_seen"])
            set_gauge("last_session_low_light_blocked_frames", runtime_signals["low_light_blocked_frames"])
            if dominant_runtime_profile:
                set_gauge("last_session_runtime_profile", dominant_runtime_profile)
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
                    "frigate_trigger_event": frigate_trigger_event,
                    "frigate_activity_hold_seconds": frigate_hold_seconds,
                    "triggered_by": getattr(self.motion_detector, "get_triggered_by", lambda: None)(),
                    "trigger_display": format_trigger_display_line(_active_names),
                    "pipeline_policy": dict(getattr(self.frame_processor, "pipeline_policy", {}) or {}),
                    "runtime_signals": {
                        **runtime_signals,
                        "yolo_ran": runtime_signals["yolo_frames_ran"] > 0,
                        "yolo_track_found": runtime_signals["yolo_frames_with_tracks"] > 0,
                        "session_extended_by_frigate": runtime_signals["session_extended_by_frigate_only"] > 0,
                        "runtime_profile": dominant_runtime_profile,
                        "runtime_profile_frames": dict(runtime_profile_counts),
                    },
                },
            )
        except Exception as e:
            inc_counter("recording_finalize_failures_total")
            logger.error(e)

        return bool(self.args.input)
