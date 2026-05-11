"""Motion detector factory with grouped trigger support and safe fallback."""

import logging

from app_config.trigger_config import TRIGGER_SOURCE_ESPHOME, TRIGGER_SOURCE_MQTT
from motion_detectors.opencv_motion import OpenCVMotionDetector
from motion_detectors.or_motion import OrMotionDetector

logger = logging.getLogger(__name__)


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
                "enabled": source in {TRIGGER_SOURCE_MQTT, TRIGGER_SOURCE_ESPHOME},
                "source": source if source in {TRIGGER_SOURCE_MQTT, TRIGGER_SOURCE_ESPHOME} else TRIGGER_SOURCE_MQTT,
                "mqtt_topic": mqtt_topic,
                "esphome_url": esphome_url,
                "esphome_sensor_id": esphome_sensor,
            },
            "scales": {"enabled": False},
        }
        frigate_detector = primary
        if primary is not None and or_extras:
            scales_detector = next((item for item in or_extras if item is not None), None)
    opencv_cfg = cfg.get("opencv") or {}
    motion_sensor_cfg = cfg.get("motion_sensor") or {}
    scales_cfg = cfg.get("scales") or {}
    frigate_cfg = cfg.get("frigate") or {}

    opencv_detector = OpenCVMotionDetector(
        capture_fn=media_source.capture,
        check_every_n_frames=int(opencv_cfg.get("check_every_n_frames") or 1),
        threshold=int(opencv_cfg.get("diff_threshold") or 18),
        min_contour_area=int(opencv_cfg.get("min_contour_area") or 320),
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

    if bool(scales_cfg.get("enabled")) and scales_detector is not None:
        detectors.append(("scales", scales_detector))

    if not detectors and bool(frigate_cfg.get("enabled")):
        logger.warning("Frigate trigger requested but unavailable; fallback to OpenCV")
        return opencv_detector
    if not detectors:
        logger.warning("No dedicated motion detector active, using OpenCV fallback")
        return opencv_detector
    if len(detectors) == 1:
        return detectors[0][1]
    return OrMotionDetector(named_detectors=detectors)
