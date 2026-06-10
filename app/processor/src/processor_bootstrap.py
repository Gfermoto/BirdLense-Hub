"""Сборка зависимостей процессора и главный цикл движения (вынесено из main.py)."""

from __future__ import annotations

import logging
import os
import threading
import time
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from typing import Optional

from api import API
from app_config.app_config import app_config
from detection_stack import build_detection_stack
from file_test_control import FileTestRuntime, maybe_build_file_test_runtime
from fps_tracker import FPSTracker
from media_runtime import ProcessorMediaSetup, setup_processor_media
from motion_runtime import build_processor_motion_detector
from detect_first import is_valid_detect_first_anchor
from detection_scheduler import (
    requires_detect_first_before_record,
    should_run_probe,
    trigger_requires_detect_first,
)
from mqtt_runtime import (
    frigate_filters_for_cameras,
    load_scales_mqtt_topic_config,
    start_mqtt_aggregator_session,
)
from processor_runtime_stats import inc_counter, set_gauge
from processor_support import check_restart_flag
from recording_finalize_worker import FinalizeWorker, maybe_start_finalize_worker
from recording_session import MotionRecordingSession
from recording_concurrency import RecordingConcurrency, concurrent_recording_enabled
from reid_runtime import prewarm_runtime_reid_model

logger = logging.getLogger(__name__)


def _start_runtime_reid_prewarm_async() -> None:
    """Warm up runtime ReID model in background without blocking motion loop startup."""

    def _run() -> None:
        try:
            prewarmed = prewarm_runtime_reid_model()
            if prewarmed:
                logger.info("Runtime ReID prewarm: ok")
            else:
                logger.info("Runtime ReID prewarm: skipped_or_failed")
        except Exception as exc:
            logger.warning("Runtime ReID prewarm failed: %s", exc)

    threading.Thread(
        target=_run,
        name="runtime-reid-prewarm",
        daemon=True,
    ).start()


@dataclass(frozen=True)
class ProcessorRunContext:
    """Всё, что нужно главному циклу и корректному закрытию медиа."""

    session: MotionRecordingSession
    media_setup: ProcessorMediaSetup
    finalize_worker: Optional[FinalizeWorker] = None
    file_test: Optional[FileTestRuntime] = None
    recording_concurrency: Optional["RecordingConcurrency"] = None
    concurrent_recording_enabled: bool = False


def parse_processor_args(argv: list[str] | None = None) -> Namespace:
    parser = ArgumentParser(description="Smart bird feeder program")
    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        help="Input source, camera/video file",
    )
    parser.add_argument(
        "--fake-motion",
        type=str,
        choices=["true", "false"],
        help="Use fake motion detector with motion or not",
    )
    parser.add_argument(
        "--mock-mqtt",
        action="store_true",
        help="Development: fake motion instead of MQTT (no broker needed)",
    )
    return parser.parse_args(argv)


def build_processor_run_context(args: Namespace) -> ProcessorRunContext:
    api = API()
    from inference_lores import resolve_inference_lores_size
    from stream_probe import probe_processor_startup, publish_probe_gauges, resolve_main_size

    startup_probe = probe_processor_startup(app_config, input_path=args.input)
    publish_probe_gauges(startup_probe)
    main_size = resolve_main_size(app_config, startup_probe)
    lores_size = resolve_inference_lores_size(app_config)

    media_setup = setup_processor_media(args, main_size, lores_size, api)

    mqtt_broker = os.environ.get("MQTT_BROKER") or app_config.get("mqtt.broker")
    mqtt_aggregator = None
    scale_weight_motion_pending = None
    frigate_detector = None
    _data_dir, scales_topic_arg, scales_unit_arg = load_scales_mqtt_topic_config()
    frigate_camera_filter, frigate_label_filter, frigate_label_exclude = frigate_filters_for_cameras(
        media_setup.cameras
    )
    use_frigate_from_aggregator = bool(mqtt_broker)
    if mqtt_broker:
        mqtt_aggregator, scale_weight_motion_pending, frigate_detector = start_mqtt_aggregator_session(
            args,
            mqtt_broker=mqtt_broker,
            frigate_camera_filter=frigate_camera_filter,
            frigate_label_filter=frigate_label_filter,
            frigate_label_exclude=frigate_label_exclude,
            scales_topic_arg=scales_topic_arg,
            scales_unit_arg=scales_unit_arg,
            data_dir=_data_dir,
        )

    motion_detector = build_processor_motion_detector(
        args,
        media_source=media_setup.media_source,
        get_media_source=media_setup.get_media_source,
        processor_cameras=media_setup.cameras,
        mqtt_broker=mqtt_broker,
        mqtt_aggregator=mqtt_aggregator,
        frigate_detector=frigate_detector,
        scale_weight_motion_pending=scale_weight_motion_pending,
        use_frigate_from_aggregator=use_frigate_from_aggregator,
        frigate_camera_filter=frigate_camera_filter,
        frigate_label_filter=frigate_label_filter,
    )

    from inference_bootstrap import record_inference_bootstrap_metrics, validate_inference_at_bootstrap

    bootstrap_plan = validate_inference_at_bootstrap(app_config)
    record_inference_bootstrap_metrics(bootstrap_plan)

    frame_processor, decision_maker, merged_overrides = build_detection_stack(
        app_config,
        save_images=bool(app_config.get("processor.save_images")),
        warn_two_stage_fallback=False,
    )
    from inference.selector import resolve_inference_backend
    from inference_bootstrap import publish_inference_backend_effective

    _requested_inf = resolve_inference_backend(app_config)
    _effective_inf = (
        str(
            getattr(getattr(frame_processor, "strategy", None), "inference_backend", "torch") or "torch",
        )
        .strip()
        .lower()
    )
    _auto_fb = _requested_inf == "auto" and _effective_inf == "torch"
    publish_inference_backend_effective(
        requested_backend=_requested_inf,
        effective_backend=_effective_inf,
        auto_fallback=_auto_fb,
    )
    finalize_worker = maybe_start_finalize_worker(app_config)
    _start_runtime_reid_prewarm_async()
    regional_species = app_config.get("processor.regional_species") or []
    if regional_species:
        api.set_active_species(regional_species)

    tracker = app_config.get("processor.tracker") or "bytetrack.yaml"
    logging.info("Using tracker: %s", tracker)
    fps_tracker = FPSTracker()

    media_source_ref = [media_setup.media_source]
    file_test = maybe_build_file_test_runtime(
        media_setup=media_setup,
        media_source_ref=media_source_ref,
        args=args,
        main_size=main_size,
        lores_size=lores_size,
    )
    session = MotionRecordingSession(
        args=args,
        api=api,
        motion_detector=motion_detector,
        mqtt_aggregator=mqtt_aggregator,
        frame_processor=frame_processor,
        decision_maker=decision_maker,
        merged_overrides=merged_overrides,
        media_source_ref=media_source_ref,
        get_media_source=media_setup.get_media_source,
        default_camera_id=media_setup.default_camera_id,
        scales_topic_arg=scales_topic_arg,
        data_dir=_data_dir,
        fps_tracker=fps_tracker,
        finalize_worker=finalize_worker,
        file_test_runtime=file_test,
    )
    registry = RecordingConcurrency()
    session.inference_lock = registry.inference_lock
    cameras = media_setup.cameras or []
    concurrent_enabled = concurrent_recording_enabled(app_config, camera_count=len(cameras))
    if concurrent_enabled:
        logger.info(
            "Concurrent per-camera recording enabled (cameras=%s)",
            len(cameras),
        )
    return ProcessorRunContext(
        session=session,
        media_setup=media_setup,
        finalize_worker=finalize_worker,
        file_test=file_test,
        recording_concurrency=registry,
        concurrent_recording_enabled=concurrent_enabled,
    )


def requeue_motion_trigger(motion_detector) -> bool:
    """Re-arm deferred trigger (OrMotionDetector, OpenCV-only, Frigate, …)."""
    fn = getattr(motion_detector, "requeue_last_trigger", None)
    if callable(fn):
        return bool(fn())
    fn = getattr(motion_detector, "mark_pending", None)
    if callable(fn):
        fn()
        return True
    return False


def _moratorium_scope_for_camera(
    camera_id: str | None,
    *,
    trigger_source: str,
) -> tuple[str, bool]:
    """Return (scope_key, is_camera_scoped) for trigger moratorium bookkeeping."""
    raw_camera = str(camera_id or "").strip()
    if raw_camera and raw_camera != "_default":
        return raw_camera, True
    source_key = str(trigger_source or "").strip().lower() or "unknown"
    return f"_unscoped:{source_key}", False


def _poll_motion(motion_detector) -> bool:
    check = getattr(motion_detector, "check", None)
    if callable(check):
        return bool(check())
    check_pending = getattr(motion_detector, "check_pending", None)
    if callable(check_pending):
        return bool(check_pending())
    return False


def _wait_for_motion(ctx: ProcessorRunContext) -> bool:
    registry = getattr(ctx, "recording_concurrency", None)
    concurrent = bool(getattr(ctx, "concurrent_recording_enabled", False) and registry is not None)
    if concurrent and registry.any_active():
        if _poll_motion(ctx.session.motion_detector):
            return True
        time.sleep(0.05)
        return False
    return bool(ctx.session.motion_detector.detect())


def _run_recording_session(
    ctx: ProcessorRunContext,
    *,
    camera_key: str,
    camera_id: str | None,
    trigger_source: str,
    last_recording_end_by_camera: dict[str, float],
    detect_first_anchor: dict | None = None,
    concurrent_context: dict | None = None,
) -> bool:
    registry = getattr(ctx, "recording_concurrency", None)

    def _finish() -> None:
        if registry is not None:
            registry.unregister(camera_key)
        last_recording_end_by_camera[camera_key] = time.monotonic()

    try:
        return bool(
            ctx.session.run(
                forced_camera_id=camera_id,
                forced_trigger_source=trigger_source or None,
                detect_first_anchor=detect_first_anchor,
                concurrent_context=concurrent_context,
            )
        )
    finally:
        _finish()


def run_motion_loop(ctx: ProcessorRunContext) -> None:
    """Бесконечный цикл движения; выход при ``session.run()`` → True (режим файла) или SystemExit."""
    last_recording_end_by_camera: dict[str, float] = {}
    last_trigger_start_by_camera: dict[str, float] = {}
    last_trigger_source_by_camera: dict[str, str] = {}
    cooldown = float(app_config.get("processor.min_seconds_between_recordings") or 0)
    trigger_moratorium = float(
        app_config.get("detection.trigger_moratorium_seconds")
        or app_config.get("processor.trigger_moratorium_seconds")
        or 0
    )
    while True:
        check_restart_flag()
        ft = ctx.file_test
        if ft is not None:
            ft.poll()
            if not ft.armed:
                time.sleep(0.25)
                continue
        if not _wait_for_motion(ctx):
            continue
        from processor_support import mark_motion_triggered

        mark_motion_triggered()
        from motion_recording_camera import resolve_motion_recording_camera_id

        camera_id = resolve_motion_recording_camera_id(
            ctx.session.motion_detector,
            mqtt_aggregator=getattr(ctx.session, "mqtt_aggregator", None),
            default_camera_id=getattr(ctx.session, "default_camera_id", None),
        )
        trigger_source = (
            str(getattr(ctx.session.motion_detector, "get_triggered_by", lambda: "")() or "").strip().lower()
        )
        detect_first_anchor = None
        session_args = getattr(ctx.session, "args", None)
        registry = getattr(ctx, "recording_concurrency", None)
        concurrent = bool(getattr(ctx, "concurrent_recording_enabled", False) and registry is not None)
        if requires_detect_first_before_record(args=session_args, app_config=app_config):
            if not trigger_requires_detect_first(trigger_source=trigger_source, app_config=app_config):
                detect_first_anchor = None
            else:
                detect_first = getattr(ctx.session, "detect_until_confirmed", None)
                if not callable(detect_first):
                    logger.error(
                        "Go2RTC requires detect_until_confirmed; skipping trigger (source=%s camera=%s)",
                        trigger_source or "?",
                        camera_id,
                    )
                    continue
                detect_first_anchor = detect_first(
                    camera_id=camera_id,
                    trigger_source=trigger_source,
                )
                if not is_valid_detect_first_anchor(detect_first_anchor):
                    logger.info(
                        "Skipping recording: no confirmed lores anchor (trigger=%s camera=%s)",
                        trigger_source or "?",
                        camera_id,
                    )
                    try:
                        ctx.session.api.activity_log(
                            "detect_first_no_anchor",
                            {
                                "camera": str(camera_id or "").strip() or None,
                                "trigger_source": trigger_source or None,
                            },
                        )
                    except Exception:
                        logger.debug("detect_first_no_anchor activity log failed", exc_info=True)
                    continue
        elif should_run_probe(trigger_source=trigger_source, app_config=app_config, args=session_args):
            probe_ok = bool(
                ctx.session.run_detection_probe_window(
                    camera_id=camera_id,
                    trigger_source=trigger_source,
                )
            )
            if not probe_ok:
                logger.info(
                    "Skipping recording after detect-probe: trigger=%s camera=%s",
                    trigger_source or "?",
                    camera_id,
                )
                continue
        camera_key, camera_scoped = _moratorium_scope_for_camera(
            camera_id,
            trigger_source=trigger_source,
        )
        moratorium_wait = 0.0
        if trigger_moratorium > 0 and camera_scoped:
            moratorium_wait = recording_cooldown_remaining(
                last_recording_end=last_trigger_start_by_camera.get(
                    camera_key,
                    0.0,
                ),
                cooldown=trigger_moratorium,
            )
        elif trigger_moratorium > 0 and not camera_scoped:
            inc_counter("recording_trigger_moratorium_unscoped_total")
            logger.warning(
                "Skipping trigger moratorium: unresolved camera (source=%s, camera_id=%s)",
                trigger_source or "?",
                str(camera_id or "").strip() or "_default",
            )
        if moratorium_wait > 0:
            requeued = requeue_motion_trigger(ctx.session.motion_detector)
            inc_counter("recording_trigger_deferred_moratorium_total")
            winner_source = str(last_trigger_source_by_camera.get(camera_key) or "").strip().lower()
            winner_start = float(last_trigger_start_by_camera.get(camera_key) or 0.0)
            elapsed_since_winner_s = max(0.0, time.monotonic() - winner_start) if winner_start > 0 else None
            logger.info(
                "Skipping competing trigger for camera=%s: trigger moratorium %.2fs (requeued=%s, source=%s)",
                camera_key,
                trigger_moratorium,
                requeued,
                trigger_source or "?",
            )
            try:
                ctx.session.api.activity_log(
                    "trigger_moratorium",
                    {
                        "camera": camera_key,
                        "trigger_source": trigger_source or None,
                        "winner_trigger_source": winner_source or None,
                        "elapsed_since_winner_s": (
                            None if elapsed_since_winner_s is None else float(round(elapsed_since_winner_s, 3))
                        ),
                        "moratorium_seconds": float(trigger_moratorium),
                        "wait_seconds": float(round(moratorium_wait, 3)),
                        "requeued": bool(requeued),
                    },
                )
            except Exception:
                logger.debug(
                    "Failed to write trigger_moratorium activity log",
                    exc_info=True,
                )
            time.sleep(moratorium_wait)
            continue
        wait = 0.0
        if cooldown > 0 and camera_scoped:
            wait = recording_cooldown_remaining(
                last_recording_end=last_recording_end_by_camera.get(
                    camera_key,
                    0.0,
                ),
                cooldown=cooldown,
            )
        elif cooldown > 0 and not camera_scoped:
            inc_counter("recording_trigger_cooldown_unscoped_total")
            logger.warning(
                "Skipping per-camera cooldown: unresolved camera (source=%s, camera_id=%s)",
                trigger_source or "?",
                str(camera_id or "").strip() or "_default",
            )
        if wait > 0:
            elapsed = cooldown - wait
            requeued = requeue_motion_trigger(ctx.session.motion_detector)
            logger.info(
                "Skipping motion trigger for camera=%s: processor.min_seconds_between_recordings=%.1fs "
                "(%.1fs since last clip on this camera, requeued=%s)",
                camera_key,
                cooldown,
                elapsed,
                requeued,
            )
            time.sleep(wait)
            continue
        finalize_worker = getattr(ctx, "finalize_worker", None)
        if finalize_worker is not None and finalize_worker.is_saturated():
            depth = finalize_worker.queue_depth()
            requeued = requeue_motion_trigger(ctx.session.motion_detector)
            inc_counter("recording_trigger_deferred_finalize_backpressure_total")
            set_gauge("finalize_queue_depth", depth)
            logger.info(
                "Deferring motion trigger: finalize queue saturated (depth=%s, requeued=%s)",
                depth,
                requeued,
            )
            time.sleep(0.5)
            continue
        ctx.session.api.notify_motion()
        should_stop = False
        last_trigger_start_by_camera[camera_key] = time.monotonic()
        if trigger_source:
            last_trigger_source_by_camera[camera_key] = trigger_source

        registry = getattr(ctx, "recording_concurrency", None)
        concurrent = bool(getattr(ctx, "concurrent_recording_enabled", False) and registry is not None)
        other_active = bool(concurrent and registry.any_active())
        if registry is not None and not registry.try_register(camera_key):
            requeued = requeue_motion_trigger(ctx.session.motion_detector)
            inc_counter("recording_trigger_deferred_camera_busy_total")
            logger.info(
                "Skipping motion trigger for camera=%s: recording already active (requeued=%s)",
                camera_key,
                requeued,
            )
            continue

        concurrent_context = None
        if registry is not None:
            concurrent_context = {
                "started_concurrent": bool(other_active),
                **registry.snapshot(exclude=camera_key),
            }

        if concurrent and other_active:
            inc_counter("recording_concurrent_session_started_total")

            def _async_recording() -> None:
                try:
                    _run_recording_session(
                        ctx,
                        camera_key=camera_key,
                        camera_id=camera_id,
                        trigger_source=trigger_source,
                        last_recording_end_by_camera=last_recording_end_by_camera,
                        detect_first_anchor=detect_first_anchor,
                        concurrent_context=concurrent_context,
                    )
                except Exception:
                    logger.exception(
                        "Concurrent recording failed for camera=%s",
                        camera_key,
                    )

            threading.Thread(
                target=_async_recording,
                daemon=True,
                name=f"birdlense-recording-{camera_key}",
            ).start()
            continue

        try:
            should_stop = _run_recording_session(
                ctx,
                camera_key=camera_key,
                camera_id=camera_id,
                trigger_source=trigger_source,
                last_recording_end_by_camera=last_recording_end_by_camera,
                detect_first_anchor=detect_first_anchor,
                concurrent_context=concurrent_context,
            )
        except Exception:
            if registry is not None:
                registry.unregister(camera_key)
            raise
        if should_stop:
            break


def close_processor_media(ctx: ProcessorRunContext) -> None:
    if ctx.finalize_worker is not None:
        ctx.finalize_worker.stop(wait=True)
    if app_config.get("video.source") == "go2rtc":
        for src in ctx.media_setup.media_sources_cache.values():
            src.close()
    else:
        ctx.media_setup.media_source.close()


def recording_cooldown_remaining(
    *,
    last_recording_end: float,
    cooldown: float,
    now_monotonic: float | None = None,
) -> float:
    """Return remaining seconds before a new recording may start."""
    if cooldown <= 0 or last_recording_end <= 0:
        return 0.0
    now = time.monotonic() if now_monotonic is None else float(now_monotonic)
    elapsed = max(0.0, now - float(last_recording_end))
    return max(0.0, float(cooldown) - elapsed)
