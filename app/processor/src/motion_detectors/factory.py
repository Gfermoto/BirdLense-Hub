"""Motion detector factory with safe local fallback."""

from motion_detectors.opencv_motion import OpenCVMotionDetector
from motion_detectors.or_motion import OrMotionDetector


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
):
    """Build the effective motion detector chain for the processor."""
    additional = None
    source = (motion_source or 'frigate').strip().lower()

    if source in {'frigate', 'opencv'}:
        additional = OpenCVMotionDetector(
            capture_fn=media_source.capture,
            check_every_n_frames=check_every_n_frames,
        )
    elif source == 'mqtt' and mqtt_broker and (mqtt_topic or '').strip():
        from motion_detectors.mqtt_binary import MQTTBinaryMotionDetector

        additional = MQTTBinaryMotionDetector(
            broker=mqtt_broker,
            port=mqtt_port,
            topic=(mqtt_topic or '').strip(),
            username=mqtt_username,
            password=mqtt_password,
        )
        additional.start()
    elif source == 'esphome' and esphome_url and esphome_sensor:
        from motion_detectors.esphome_binary import ESPHomeBinaryMotionDetector

        additional = ESPHomeBinaryMotionDetector(
            url=esphome_url,
            sensor_id=esphome_sensor,
        )

    if primary and additional:
        return OrMotionDetector(primary=primary, additional=additional)
    if primary:
        return primary
    if additional:
        return additional
    return OpenCVMotionDetector(
        capture_fn=media_source.capture,
        check_every_n_frames=check_every_n_frames,
    )
