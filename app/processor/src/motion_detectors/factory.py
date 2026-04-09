"""Motion detector factory with safe local fallback."""

import logging

from motion_detectors.opencv_motion import OpenCVMotionDetector
from motion_detectors.or_motion import OrMotionDetector

logger = logging.getLogger(__name__)


def build_motion_detector(
    *,
    motion_source,
    media_source,
    primary=None,
    mqtt_broker=None,
    mqtt_topic='',
    mqtt_port=1883,
    mqtt_username=None,
    mqtt_password=None,
    esphome_url='',
    esphome_sensor='',
    check_every_n_frames=1,
    or_extras=None,
    opencv_threshold=25,
    opencv_min_contour_area=500,
):
    """Build the effective motion detector chain for the processor."""
    additional = None
    source = (motion_source or 'frigate').strip().lower()

    opencv_detector = OpenCVMotionDetector(
        capture_fn=media_source.capture,
        check_every_n_frames=check_every_n_frames,
        threshold=int(opencv_threshold),
        min_contour_area=int(opencv_min_contour_area),
    )
    # OpenCV parallel to Frigate only when Frigate MQTT path is actually active.
    # If broker/topic is missing or Frigate client is None, OpenCV must become the
    # real trigger — not a second detector OR-ed with a dead primary.
    if source == 'frigate' and primary:
        additional = opencv_detector
    elif source == 'opencv':
        additional = opencv_detector
    elif source == 'mqtt' and mqtt_broker and (mqtt_topic or '').strip():
        try:
            from motion_detectors.mqtt_binary import MQTTBinaryMotionDetector

            additional = MQTTBinaryMotionDetector(
                broker=mqtt_broker,
                port=mqtt_port,
                topic=(mqtt_topic or '').strip(),
                username=mqtt_username,
                password=mqtt_password,
            )
            additional.start()
        except (ImportError, ModuleNotFoundError, Exception) as exc:
            logger.warning(
                'MQTT motion detector unavailable, fallback to OpenCV: %s',
                exc,
            )
            additional = None
    elif source == 'esphome' and esphome_url and esphome_sensor:
        try:
            from motion_detectors.esphome_binary import ESPHomeBinaryMotionDetector

            additional = ESPHomeBinaryMotionDetector(
                url=esphome_url,
                sensor_id=esphome_sensor,
            )
        except (ImportError, ModuleNotFoundError, Exception) as exc:
            logger.warning(
                'ESPHome motion detector unavailable, fallback to OpenCV: %s',
                exc,
            )
            additional = None

    extra_list = [e for e in (or_extras or []) if e is not None]
    if primary and (additional is not None or extra_list):
        return OrMotionDetector(
            primary=primary, additional=additional, extras=extra_list,
        )
    if primary:
        return primary
    if additional:
        return additional
    logger.warning(
        'No dedicated motion detector active, using OpenCV fallback '
        '(source=%s, check_every_n_frames=%s)',
        source,
        check_every_n_frames,
    )
    return opencv_detector
