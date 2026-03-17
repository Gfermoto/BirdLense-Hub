import logging
import numpy as np
import cv2
import time


class LightLevelDetector:
    """Simple detector for checking if there's enough light for processing."""

    def __init__(self, min_brightness=25, min_contrast=20, sample_rate=8):
        self.min_brightness = min_brightness
        self.min_contrast = min_contrast
        self.sample_rate = sample_rate
        self.last_log_time = None
        self.logger = logging.getLogger(__name__)

    def has_sufficient_light(self, frame):
        try:
            gray = cv2.cvtColor(
                frame[::self.sample_rate, ::self.sample_rate], cv2.COLOR_BGR2GRAY)
            mean_brightness = gray.mean()
            if mean_brightness < self.min_brightness:
                self._log_conditions(mean_brightness)
                return False
            contrast = gray.std()
            is_sufficient = contrast >= self.min_contrast

            if not is_sufficient:
                self._log_conditions(mean_brightness, contrast)

            return is_sufficient

        except Exception as e:
            self.logger.error(f'Error checking light levels: {e}')
            return True

    def _log_conditions(self, brightness, contrast=None):
        """Rate-limited logging of lighting conditions"""
        current_time = time.time()
        if not self.last_log_time or current_time - self.last_log_time > 60:
            if contrast is None:
                self.logger.info(f'Insufficient brightness: {brightness:.1f}')
            else:
                self.logger.info(
                    f'Poor lighting conditions: brightness={brightness:.1f}, '
                    f'contrast={contrast:.1f}'
                )
            self.last_log_time = current_time
