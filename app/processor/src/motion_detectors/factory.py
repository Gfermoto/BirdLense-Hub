"""Motion detector factory with grouped trigger support and safe fallback."""

import logging

from app_config.trigger_config import TRIGGER_SOURCE_ESPHOME, TRIGGER_SOURCE_MQTT
from motion_detectors.opencv_camera_masks import resolve_opencv_mask_specs
from motion_detectors.opencv_live_overlay import register_opencv_live_detector
from motion_detectors.opencv_motion import OpenCVMotionDetector
from motion_detectors.opencv_multi_camera import OpenCVMultiCameraMotionDetector
from motion_detectors.or_motion import OrMotionDetector
from processor_runtime_stats import inc_counter

logger = logging.getLogger(__name__)


def _opencv_float(opencv_cfg: dict, key: str, default: float) -> float:
    try:
        raw = opencv_cfg.get(key)
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _build_opencv_motion_detector(
    *,
    capture_fn,
    motion_masks: list[str],
    opencv_cfg: dict,
    camera_id: str = "",
) -> OpenCVMotionDetector:
    detector = OpenCVMotionDetector(
        capture_fn=capture_fn,
        camera_id=camera_id,
        check_every_n_frames=int(opencv_cfg.get("check_every_n_frames") or 1),
        check_interval=float(opencv_cfg.get("check_interval_seconds") or 0.12),
        motion_max_side_px=int(opencv_cfg.get("motion_max_side_px") or 512),
        threshold=int(opencv_cfg.get("diff_threshold") or 18),
        min_contour_area=int(opencv_cfg.get("min_contour_area") or 320),
        global_motion_mean_absdiff=_opencv_float(opencv_cfg, "global_motion_mean_absdiff", 2.5),
        min_motion_pixel_fraction=_opencv_float(opencv_cfg, "min_motion_pixel_fraction", 0.0008),
        max_contour_area_frac=_opencv_float(opencv_cfg, "max_contour_area_frac", 0.38),
        smart_trigger_enabled=bool(opencv_cfg.get("smart_trigger_enabled", True)),
        detection_method=str(opencv_cfg.get("detection_method") or "frame_diff"),
        suppress_warmup_frames=int(opencv_cfg.get("suppress_warmup_frames") or 0),
        auto_profile_enabled=bool(opencv_cfg.get("auto_profile_enabled", False)),
        auto_profile_night_luma_threshold=_opencv_float(
            opencv_cfg, "auto_profile_night_luma_threshold", 58.0
        ),
        day_diff_threshold=int(
            opencv_cfg.get("day_diff_threshold") or int(opencv_cfg.get("diff_threshold") or 18)
        ),
        day_min_contour_area=int(
            opencv_cfg.get("day_min_contour_area") or int(opencv_cfg.get("min_contour_area") or 320)
        ),
        day_global_motion_mean_absdiff=_opencv_float(
            opencv_cfg, "day_global_motion_mean_absdiff", 2.5
        ),
        day_min_motion_pixel_fraction=_opencv_float(
            opencv_cfg, "day_min_motion_pixel_fraction", 0.0008
        ),
        day_max_contour_area_frac=_opencv_float(opencv_cfg, "day_max_contour_area_frac", 0.38),
        night_diff_threshold=int(
            opencv_cfg.get("night_diff_threshold") or int(opencv_cfg.get("diff_threshold") or 18)
        ),
        night_min_contour_area=int(
            opencv_cfg.get("night_min_contour_area") or int(opencv_cfg.get("min_contour_area") or 320)
        ),
        night_global_motion_mean_absdiff=_opencv_float(
            opencv_cfg, "night_global_motion_mean_absdiff", 2.2
        ),
        night_min_motion_pixel_fraction=_opencv_float(
            opencv_cfg, "night_min_motion_pixel_fraction", 0.0006
        ),
        night_max_contour_area_frac=_opencv_float(opencv_cfg, "night_max_contour_area_frac", 0.45),
        mog2_history=int(opencv_cfg.get("mog2_history") or 300),
        mog2_var_threshold=_opencv_float(opencv_cfg, "mog2_var_threshold", 24.0),
        mog2_detect_shadows=bool(opencv_cfg.get("mog2_detect_shadows", False)),
        mog2_min_motion_pixel_fraction=_opencv_float(
            opencv_cfg, "mog2_min_motion_pixel_fraction", 0.0006
        ),
        mog2_min_contour_area=int(
            opencv_cfg.get("mog2_min_contour_area") or int(opencv_cfg.get("min_contour_area") or 320)
        ),
        motion_masks=motion_masks,
        min_consecutive_motion_frames=int(opencv_cfg.get("min_consecutive_motion_frames") or 2),
        scene_change_motion_fraction=_opencv_float(opencv_cfg, "scene_change_motion_fraction", 0.8),
        improve_contrast=bool(opencv_cfg.get("improve_contrast", False)),
        morphology_open_iterations=int(opencv_cfg.get("morphology_open_iterations") or 1),
    )
    if camera_id:
        register_opencv_live_detector(camera_id, detector)
    return detector


def _build_opencv_detector_bundle(
    *,
    opencv_cfg: dict,
    media_source,
    get_media_source=None,
    processor_cameras=None,
    cameras_config=None,
) -> OpenCVMotionDetector | OpenCVMultiCameraMotionDetector:
    cam_rows = list(processor_cameras or [])
    raw_config = list(cameras_config or [])

    if callable(get_media_source) and len(cam_rows) > 1:
        multi: list[tuple[str, OpenCVMotionDetector]] = []
        for cam in cam_rows:
            cid = str(cam.get("id") or "").strip()
            if not cid:
                continue
            src = get_media_source(cid)
            masks = resolve_opencv_mask_specs(
                camera_id=cid,
                cameras_config=raw_config,
            )
            multi.append(
                (
                    cid,
                    _build_opencv_motion_detector(
                        capture_fn=src.capture,
                        motion_masks=masks,
                        opencv_cfg=opencv_cfg,
                        camera_id=cid,
                    ),
                )
            )
        if multi:
            if len(multi) == 1:
                return multi[0][1]
            return OpenCVMultiCameraMotionDetector(multi)

    primary_id = str(cam_rows[0].get("id") or "").strip() if cam_rows else None
    masks = resolve_opencv_mask_specs(
        camera_id=primary_id or None,
        cameras_config=raw_config,
    )
    return _build_opencv_motion_detector(
        capture_fn=media_source.capture,
        motion_masks=masks,
        opencv_cfg=opencv_cfg,
        camera_id=primary_id or "",
    )


def build_motion_detector(
    *,
    trigger_config=None,
    media_source,
    frigate_detector=None,
    mqtt_broker=None,
    mqtt_port=1883,
    mqtt_username=None,
    mqtt_password=None,
    scales_detector=None,
    motion_source=None,
    primary=None,
    mqtt_topic="",
    esphome_url="",
    esphome_sensor="",
    check_every_n_frames=1,
    or_extras=None,
    opencv_threshold=25,
    opencv_min_contour_area=500,
    get_media_source=None,
    processor_cameras=None,
    cameras_config=None,
):
    """Build the effective motion detector chain for the processor."""
    cfg = trigger_config or {}
    legacy_force_primary = False
    if not cfg:
        source = str(motion_source or "opencv").strip().lower()
        legacy_force_primary = primary is not None and source == "opencv"
        cfg = {
            "opencv": {
                "enabled": source in {"opencv", "frigate"},
                "check_every_n_frames": check_every_n_frames,
                "diff_threshold": opencv_threshold,
                "min_contour_area": opencv_min_contour_area,
            },
            "frigate": {
                "enabled": source in {"opencv", "frigate"} and primary is not None,
                "topic": mqtt_topic or "__legacy__",
            },
            "motion_sensor": {
                "enabled": source in {TRIGGER_SOURCE_MQTT, TRIGGER_SOURCE_ESPHOME, "pir"},
                "source": (
                    source
                    if source in {TRIGGER_SOURCE_MQTT, TRIGGER_SOURCE_ESPHOME, "pir"}
                    else TRIGGER_SOURCE_MQTT
                ),
                "mqtt_topic": mqtt_topic,
                "esphome_url": esphome_url,
                "esphome_sensor_id": esphome_sensor,
                "pir_pin": 4,
            },
            "scales": {"enabled": False},
        }
        frigate_detector = primary
        if primary is not None and or_extras:
            scales_detector = next((item for item in or_extras if item is not None), None)
    opencv_cfg = cfg.get("opencv") or {}
    if bool(opencv_cfg.get("enabled")):
        logger.info(
            "OpenCV trigger runtime: method=%s auto_profile=%s warmup=%s "
            "every_n=%s max_side=%spx interval=%.2fs smart=%s",
            opencv_cfg.get("detection_method"),
            opencv_cfg.get("auto_profile_enabled"),
            opencv_cfg.get("suppress_warmup_frames"),
            opencv_cfg.get("check_every_n_frames"),
            opencv_cfg.get("motion_max_side_px"),
            float(opencv_cfg.get("check_interval_seconds") or 0.12),
            opencv_cfg.get("smart_trigger_enabled"),
        )
    motion_sensor_cfg = cfg.get("motion_sensor") or {}
    scales_cfg = cfg.get("scales") or {}
    frigate_cfg = cfg.get("frigate") or {}

    opencv_detector = _build_opencv_detector_bundle(
        opencv_cfg=opencv_cfg,
        media_source=media_source,
        get_media_source=get_media_source,
        processor_cameras=processor_cameras,
        cameras_config=cameras_config,
    )

    detectors: list[tuple[str, object]] = []
    if (
        bool(frigate_cfg.get("enabled"))
        and frigate_detector
        and (legacy_force_primary or (mqtt_broker and str(frigate_cfg.get("topic") or "").strip()))
    ):
        detectors.append(("frigate", frigate_detector))

    if bool(opencv_cfg.get("enabled")):
        detectors.append(("opencv", opencv_detector))

    if bool(motion_sensor_cfg.get("enabled")):
        source = str(motion_sensor_cfg.get("source") or TRIGGER_SOURCE_MQTT).strip().lower()
        if source == TRIGGER_SOURCE_MQTT and mqtt_broker and str(motion_sensor_cfg.get("mqtt_topic") or "").strip():
            try:
                from motion_detectors.mqtt_binary import MQTTBinaryMotionDetector

                motion_detector = MQTTBinaryMotionDetector(
                    broker=mqtt_broker,
                    port=mqtt_port,
                    topic=str(motion_sensor_cfg.get("mqtt_topic") or "").strip(),
                    username=mqtt_username,
                    password=mqtt_password,
                )
                motion_detector.start()
                detectors.append(("motion_sensor", motion_detector))
            except (ImportError, ModuleNotFoundError, Exception) as exc:
                logger.warning(
                    "MQTT motion detector unavailable, skip grouped motion sensor: %s",
                    exc,
                )
        elif (
            source == TRIGGER_SOURCE_ESPHOME
            and str(motion_sensor_cfg.get("esphome_url") or "").strip()
            and str(motion_sensor_cfg.get("esphome_sensor_id") or "").strip()
        ):
            try:
                from motion_detectors.esphome_binary import ESPHomeBinaryMotionDetector

                detectors.append(
                    (
                        "motion_sensor",
                        ESPHomeBinaryMotionDetector(
                            url=str(motion_sensor_cfg.get("esphome_url") or "").strip(),
                            sensor_id=str(motion_sensor_cfg.get("esphome_sensor_id") or "").strip(),
                        ),
                    )
                )
            except (ImportError, ModuleNotFoundError, Exception) as exc:
                logger.warning(
                    "ESPHome motion detector unavailable, skip grouped motion sensor: %s",
                    exc,
                )
        elif source == "pir":
            try:
                from motion_detectors.pir import PIRMotionDetector

                detectors.append(
                    (
                        "motion_sensor",
                        PIRMotionDetector(
                            pin=int(motion_sensor_cfg.get("pir_pin") or 4)
                        ),
                    )
                )
            except (ImportError, ModuleNotFoundError, Exception) as exc:
                logger.warning(
                    "PIR motion detector unavailable, skip grouped motion sensor: %s",
                    exc,
                )

    if bool(scales_cfg.get("enabled")) and scales_detector is not None:
        detectors.append(("scales", scales_detector))

    if not detectors and bool(frigate_cfg.get("enabled")):
        inc_counter("trigger_motion_factory_frigate_fallback_opencv_total")
        logger.warning("Frigate trigger requested but unavailable; fallback to OpenCV")
        return opencv_detector
    if not detectors:
        inc_counter("trigger_motion_factory_opencv_fallback_total")
        logger.warning("No dedicated motion detector active, using OpenCV fallback")
        return opencv_detector
    if len(detectors) == 1:
        return detectors[0][1]
    return OrMotionDetector(named_detectors=detectors)
