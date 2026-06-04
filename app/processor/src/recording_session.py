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
from app_config.cameras import get_valid_cameras
from app_config.trigger_config import format_trigger_display_line, get_active_trigger_names
from birdnet_mqtt_confidence import merge_birdnet_mqtt_bias_into_overrides
from fps_tracker import FPSTracker
from processor_support import get_output_path, processor_status
from processor_runtime_stats import inc_counter, observe_timing, set_gauge
from detection_strategy import coerce_bgr_frame
from recording_session_policy import effective_frigate_hold_seconds
from recording_finalize_worker import FinalizeWorker
from session_state_repository import SessionStateRepository
from detection_scheduler import build_probe_config
from yolo_blind_monitor import YoloBlindLiveMonitor, run_blind_quickcheck

logger = logging.getLogger(__name__)


def _camera_processor_overrides(camera_id: str | None) -> dict:
    """Per-camera processor overrides from ``processor.camera_overrides.<camera_id>``."""
    cam = str(camera_id or "").strip()
    if not cam:
        return {}
    raw = app_config.get(f"processor.camera_overrides.{cam}")
    merged = dict(raw) if isinstance(raw, dict) else {}
    cameras = get_valid_cameras(video_config=(app_config.get("video") or {}))
    if isinstance(cameras, list):
        for row in cameras:
            if not isinstance(row, dict):
                continue
            if str(row.get("id") or "").strip() != cam:
                continue
            zones = row.get("detection_interest_zones")
            if zones is not None:
                merged["processor.detection_interest_zones"] = zones
                merged["processor.detection_interest_zones_required"] = bool(zones)
            break
    return merged


def _camera_slot_for_id(camera_id: str | None) -> str | None:
    cam = str(camera_id or "").strip()
    if not cam:
        return None
    cameras = get_valid_cameras(video_config=(app_config.get("video") or {}))
    for row in cameras:
        if str(row.get("id") or "").strip() != cam:
            continue
        slot = str(row.get("camera_slot") or "").strip()
        return slot or None
    return None


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
        finalize_worker: FinalizeWorker | None = None,
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
        self.finalize_worker = finalize_worker
        self.file_test_runtime = file_test_runtime
        self.inference_lock = None
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

    def _frigate_prior_active(
        self,
        *,
        camera_id: str | None,
        frigate_hold_seconds: float,
    ) -> bool:
        if frigate_hold_seconds <= 0:
            return False
        recent_frigate = getattr(self.motion_detector, "has_recent_frigate_activity", None)
        if callable(recent_frigate):
            try:
                return bool(recent_frigate(camera=camera_id, max_age_seconds=frigate_hold_seconds))
            except Exception:
                pass
        aggregator_recent = getattr(self.mqtt_aggregator, "has_recent_frigate_activity", None)
        if callable(aggregator_recent):
            camera_ids = self._session_activity_camera_ids(camera_id)
            try:
                return bool(
                    aggregator_recent(
                        camera_ids=camera_ids,
                        max_age_seconds=frigate_hold_seconds,
                        min_confidence=0.0,
                    )
                )
            except Exception:
                pass
        return False

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

    def run_detection_probe_window(self, *, camera_id: str | None, trigger_source: str | None) -> bool:
        """Run bounded detect-only loop before recording when trigger is in scheduler list."""
        cfg = build_probe_config(app_config)
        if not cfg.enabled:
            return True
        trigger = str(trigger_source or "").strip().lower()
        if trigger not in set(cfg.triggers):
            return True
        if not self.args.input and app_config.get("video.source") == "go2rtc":
            self.media_source = self.get_media_source(camera_id or self.default_camera_id)
        start = time.monotonic()
        frames = 0
        hits = 0
        # Isolate probe from regular track accumulation.
        self.frame_processor.reset()
        while frames < cfg.max_frames and (time.monotonic() - start) <= cfg.window_seconds:
            frame = self.media_source.capture()
            if frame is None:
                time.sleep(0.03)
                continue
            frames += 1
            if self.frame_processor.run(frame, frame_time=None, skip_light_gate=False):
                hits += 1
                break
        self.frame_processor.reset()
        logger.info(
            "detection_probe: trigger=%s camera=%s frames=%s hits=%s window=%.2fs",
            trigger or "?",
            camera_id or "?",
            frames,
            hits,
            cfg.window_seconds,
        )
        return (hits > 0) if cfg.start_recording_on_positive else True

    def run(
        self,
        *,
        forced_camera_id: str | None = None,
        forced_trigger_source: str | None = None,
        concurrent_context: dict[str, Any] | None = None,
    ) -> bool:
        """Выполнить одну запись. Возвращает True, если внешний цикл main должен завершиться (режим --input)."""
        session_overrides = merge_birdnet_mqtt_bias_into_overrides(
            self.merged_overrides, app_config, self.mqtt_aggregator
        )
        self.decision_maker.species_confidence_overrides = session_overrides

        from motion_recording_camera import resolve_motion_recording_camera_id

        camera_id = (
            str(forced_camera_id).strip()
            if forced_camera_id
            else resolve_motion_recording_camera_id(
                self.motion_detector,
                mqtt_aggregator=self.mqtt_aggregator,
                default_camera_id=self.default_camera_id,
            )
        )
        frigate_trigger_event = None
        trigger_by = (
            str(forced_trigger_source or "").strip().lower()
            or str(getattr(self.motion_detector, "get_triggered_by", lambda: None)() or "").strip().lower()
        )
        if trigger_by == "frigate":
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
            from recording_session_manifest import write_recording_started

            write_recording_started(
                output_path_physical,
                video_path_logical=video_path_for_api,
                start_time=start_time,
                camera_id=camera_id,
                camera_slot=_camera_slot_for_id(camera_id),
                trigger_source=str(forced_trigger_source or "").strip().lower() or None,
            )
        except Exception:
            logger.debug("session manifest write failed", exc_info=True)
        session_trigger_perf = time.perf_counter()

        trace_writer = None
        try:
            from frame_decision_trace import open_session_trace, set_session_trace_writer

            if bool(app_config.get("processor.frame_decision_trace_enabled", True)):
                sk = datetime.now(timezone.utc).strftime("%H%M%S")
                trace_writer = open_session_trace(
                    Path(self.data_dir),
                    session_key=sk,
                    camera_id=camera_id,
                )
                set_session_trace_writer(trace_writer)
        except Exception:
            logger.debug("frame decision trace init failed", exc_info=True)

        try:
            from pipeline_config import build_motion_trigger_context

            trigger_ctx = build_motion_trigger_context(
                self.motion_detector,
                app_config,
                media_source=self.media_source,
            )
            self.frame_processor.set_session_context(trigger_ctx.as_dict())
            main_size = getattr(self.media_source, "main_size", None)
            if main_size and len(main_size) >= 2:
                try:
                    pw, ph = int(main_size[0]), int(main_size[1])
                    if pw > 0 and ph > 0:
                        self.frame_processor.strategy.set_playback_frame_shape((ph, pw))
                except (TypeError, ValueError):
                    pass
            set_gauge("recording_trigger_source", trigger_ctx.triggered_by or "unknown")
            set_gauge("recording_stream_fps", float(trigger_ctx.stream_fps))
            logger.info(
                "recording_session: trigger=%s stream_fps=%.2f model_imgsz=%s native_detect=%s",
                trigger_ctx.triggered_by or "?",
                trigger_ctx.stream_fps,
                trigger_ctx.model_imgsz,
                trigger_ctx.use_native_resolution,
            )
            self.frame_processor.reset()
            self.decision_maker.reset()
            self.fps_tracker.reset()
            inc_counter("recording_session_total")
            file_mode = (app_config.get("video.source") or "").strip().lower() == "file"
            try:
                frigate_hold_seconds = float(app_config.get("processor.frigate_activity_hold_seconds") or 0.0)
            except (TypeError, ValueError):
                frigate_hold_seconds = 0.0
            frigate_hold_seconds = effective_frigate_hold_seconds(
                frigate_hold_seconds,
                trigger_by,
            )
            try:
                max_frigate_only_extension_frames = int(
                    app_config.get("processor.frigate_only_extension_max_frames") or 0
                )
            except (TypeError, ValueError):
                max_frigate_only_extension_frames = 0
            max_frigate_only_extension_frames = max(
                0,
                max_frigate_only_extension_frames,
            )
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
                "session_frigate_only_extension_guard_drops": 0,
                "track_id_switches_count": 0,
                "avg_track_duration_sec": 0.0,
                "yolo_blind_phase": "none",
                "blind_quickcheck_frames": 0,
                "blind_quickcheck_hits": 0,
                "yolo_frames_raw_unaccepted": 0,
                "yolo_frames_raw_no_track": 0,
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
                blind_alert_seconds = float(
                    app_config.get("detection.yolo_blind_alert_seconds")
                    or app_config.get("detection.yolo_blind_min_duration_seconds")
                    or 30.0
                )
            except (TypeError, ValueError):
                blind_alert_seconds = 30.0
            blind_live_monitor = YoloBlindLiveMonitor(alert_seconds=blind_alert_seconds)
            runtime_profile_counts: Counter[str] = Counter()
            runtime_profile_overrides: dict[str, dict] = {}
            camera_overrides = _camera_processor_overrides(camera_id)
            if camera_overrides:
                self.decision_maker.apply_runtime_overrides(camera_overrides)

            def _raw_boxes_from_stats(local_stats: dict) -> int:
                return int(local_stats.get("yolo_raw_boxes") or 0)

            def _accumulate_run_stats(local_stats: dict, *, count_frame_metrics: bool = True) -> int:
                """Session-level YOLO counters; one increment per captured frame (not per quickcheck probe)."""
                raw_boxes_local = _raw_boxes_from_stats(local_stats)
                if not count_frame_metrics:
                    return raw_boxes_local
                if raw_boxes_local > 0 and runtime_signals.get("trigger_to_first_bbox_wall_s") is None:
                    runtime_signals["trigger_to_first_bbox_wall_s"] = round(
                        max(0.0, time.perf_counter() - session_trigger_perf),
                        6,
                    )
                if local_stats.get("yolo_track_found") and runtime_signals.get("trigger_to_first_track_wall_s") is None:
                    runtime_signals["trigger_to_first_track_wall_s"] = round(
                        max(0.0, time.perf_counter() - session_trigger_perf),
                        6,
                    )
                if local_stats.get("yolo_ran"):
                    runtime_signals["yolo_frames_ran"] += 1
                    processor_status["last_yolo_ok_at"] = datetime.now(timezone.utc).isoformat()
                if local_stats.get("yolo_track_found"):
                    runtime_signals["yolo_frames_with_tracks"] += 1
                    processor_status["last_yolo_detection_at"] = datetime.now(timezone.utc).isoformat()
                if raw_boxes_local > 0:
                    runtime_signals["yolo_frames_with_raw_boxes"] += 1
                    runtime_signals["yolo_raw_boxes_total"] += raw_boxes_local
                accepted_local = int(local_stats.get("yolo_accepted_boxes") or 0)
                runtime_signals["yolo_accepted_boxes_total"] += accepted_local
                if raw_boxes_local > 0 and accepted_local == 0:
                    runtime_signals["yolo_frames_raw_unaccepted"] += 1
                if raw_boxes_local > 0 and not local_stats.get("yolo_track_found"):
                    runtime_signals["yolo_frames_raw_no_track"] += 1
                runtime_signals["track_id_switches_count"] = max(
                    int(runtime_signals.get("track_id_switches_count") or 0),
                    int(local_stats.get("track_id_switches_count") or 0),
                )
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
                    raw_classifier_frame = getattr(
                        self.media_source,
                        "get_classifier_source_frame",
                        lambda: None,
                    )()
                    classifier_source_frame = coerce_bgr_frame(
                        raw_classifier_frame,
                        log_label="classifier_source_frame",
                    )
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
                scoring_overrides = dict(camera_overrides or {})
                if bool(app_config.get("processor.scoring_engine_enabled", False)):
                    scoring_overrides["_scoring_frigate_prior_active"] = self._frigate_prior_active(
                        camera_id=camera_id,
                        frigate_hold_seconds=frigate_hold_seconds,
                    )
                with self.fps_tracker:
                    lock = getattr(self, "inference_lock", None)
                    if lock is not None:
                        with lock:
                            has_detections = self.frame_processor.run(
                                frame,
                                frame_time=frame_time,
                                classification_frame=classifier_source_frame,
                                camera_overrides=scoring_overrides,
                            )
                    else:
                        has_detections = self.frame_processor.run(
                            frame,
                            frame_time=frame_time,
                            classification_frame=classifier_source_frame,
                            camera_overrides=scoring_overrides,
                        )
                run_stats = dict(getattr(self.frame_processor, "last_run_stats", {}) or {})
                if camera_id:
                    from frigate_live_track import get_frigate_live_bbox
                    from motion_detectors.opencv_live_overlay import publish_merged_detector_overlay

                    live_polygons = list(getattr(self.frame_processor, "live_detector_polygons", None) or [])
                    publish_merged_detector_overlay(
                        camera_id,
                        live_polygons,
                        frigate_bbox_norm=get_frigate_live_bbox(camera_id),
                    )
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

                # Primary-path recovery: normal frame_processor.run() produced raw boxes.
                if raw_boxes > 0:
                    runtime_signals["yolo_blind_phase"] = "recovered"
                    blind_suspected_since_monotonic = None
                    blind_quickcheck_until_monotonic = 0.0

                frigate_only_extension = bool(
                    frigate_hold_seconds > 0
                    and has_detections
                    and not raw_yolo_detections
                )
                if frigate_only_extension:
                    runtime_signals["session_extended_by_frigate_only"] += 1
                    if (
                        max_frigate_only_extension_frames > 0
                        and runtime_signals["session_extended_by_frigate_only"] > max_frigate_only_extension_frames
                    ):
                        runtime_signals["session_frigate_only_extension_guard_drops"] += 1
                        has_detections = False
                        frigate_only_extension = False
                        logger.info(
                            "recording_session: frigate-only extension guard hit (camera=%s, max_frames=%s)",
                            camera_id or "_default",
                            max_frigate_only_extension_frames,
                        )
                    suspicion_ready = (
                        runtime_signals["yolo_frames_ran"] >= max(1, blind_min_frames)
                        and runtime_signals["yolo_raw_boxes_total"] == 0
                        and runtime_signals["session_extended_by_frigate_only"] >= max(1, blind_min_frigate)
                    )
                    if suspicion_ready and runtime_signals["yolo_blind_phase"] == "none":
                        runtime_signals["yolo_blind_phase"] = "suspected"
                        blind_suspected_since_monotonic = time.monotonic()
                        blind_quickcheck_until_monotonic = blind_suspected_since_monotonic + max(
                            0.2, quickcheck_seconds
                        )

                if runtime_signals["yolo_blind_phase"] == "suspected":
                    now_m = time.monotonic()
                    if now_m <= blind_quickcheck_until_monotonic:
                        runtime_signals["blind_quickcheck_frames"] += 1
                        qc_stats = run_blind_quickcheck(
                            self.frame_processor,
                            frame,
                            cfg=app_config,
                            frame_time=frame_time,
                            classification_frame=classifier_source_frame,
                        )
                        quick_raw = _accumulate_run_stats(qc_stats, count_frame_metrics=False)
                        if quick_raw > 0:
                            runtime_signals["blind_quickcheck_hits"] += 1
                            runtime_signals["yolo_blind_phase"] = "recovered"
                            blind_suspected_since_monotonic = None
                            blind_quickcheck_until_monotonic = 0.0
                    elif runtime_signals["yolo_blind_phase"] == "suspected":
                        runtime_signals["yolo_blind_phase"] = "confirmed"

                blind_live_monitor.on_frame(
                    frigate_only_extension=frigate_only_extension,
                    yolo_track_found=bool(run_stats.get("yolo_track_found")),
                    yolo_raw_boxes=raw_boxes,
                    runtime_signals=runtime_signals,
                )

                self.decision_maker.update_has_detections(has_detections)
                self.decision_maker.get_first_species_result(
                    self.frame_processor.tracks,
                )
                if self.decision_maker.decide_stop_recording():
                    break
            self.fps_tracker.log_summary()
        finally:
            if camera_id:
                try:
                    from motion_detectors.opencv_live_overlay import set_yolo_live_overlay

                    set_yolo_live_overlay(camera_id, {"detector_polygons": []})
                except Exception:
                    logger.debug("yolo live overlay clear failed", exc_info=True)
            try:
                from frame_decision_trace import set_session_trace_writer

                if trace_writer is not None:
                    trace_writer.close()
                set_session_trace_writer(None)
            except Exception:
                logger.debug("frame decision trace close failed", exc_info=True)
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
            try:
                stability = self.frame_processor.get_tracking_stability_stats()
                runtime_signals["track_id_switches_count"] = int(stability.get("track_id_switches_count") or 0)
                runtime_signals["avg_track_duration_sec"] = float(stability.get("avg_track_duration_sec") or 0.0)
            except Exception:
                logging.debug("track stability summary failed", exc_info=True)
            finalize_kwargs = {
                "api": self.api,
                "motion_detector": self.motion_detector,
                "mqtt_aggregator": self.mqtt_aggregator,
                "frame_processor": self.frame_processor,
                "decision_maker": self.decision_maker,
                "start_time": start_time,
                "end_time": end_time,
                "output_path_physical": output_path_physical,
                "output_path_logical": output_path_logical,
                "video_output": video_output,
                "video_path_for_api": video_path_for_api,
                "scales_topic_arg": self.scales_topic_arg,
                "data_dir": self.data_dir,
                "recording_context": {
                    "triggered_camera": camera_id,
                    "camera_slot": _camera_slot_for_id(camera_id),
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
                    "concurrent_recording": dict(concurrent_context or {}),
                },
            }
            opencv_diag = getattr(self.motion_detector, "get_opencv_diagnostics", lambda: None)()
            if opencv_diag is None:
                opencv_diag = getattr(self.motion_detector, "diagnostics", lambda: None)()
            if isinstance(opencv_diag, dict):
                finalize_kwargs["recording_context"]["runtime_signals"]["opencv_trigger_diagnostics"] = opencv_diag
            if self.finalize_worker is not None:
                if self.finalize_worker.enqueue(finalize_kwargs):
                    logger.info("recording_session: finalize task enqueued (async worker mode)")
                else:
                    # Backpressure fallback: never drop finalized clip; run sync as safety net.
                    logger.warning("recording_session: finalize queue full, fallback to synchronous finalize")
                    finalize_motion_recording(**finalize_kwargs)
            else:
                finalize_motion_recording(**finalize_kwargs)
        except Exception as e:
            inc_counter("recording_finalize_failures_total")
            logger.error(e)

        return bool(self.args.input)
