import time
import math
import logging
import cv2
import numpy as np
from light_level_detector import LightLevelDetector
from detection_strategy import DetectionStrategy
from app_config.app_config import app_config

class FrameProcessor:
    def __init__(self, detection_strategy: DetectionStrategy, save_images=False, tracker='bytetrack.yaml'):
        self.save_images = save_images
        self.tracker = tracker
        self.logger = logging.getLogger(__name__)
        self.light_detector = LightLevelDetector()
        
        self.strategy = detection_strategy
        
        self.logger.info('FrameProcessor initialized.')
        self.reset()

    def run(self, img, frame_time=None):
        """
        Process frame. frame_time: optional seconds (for video file); else uses elapsed real time.
        """
        if img is None:
            raise Exception('Frame is missing')
        self.cnt += 1
        
        if frame_time is None:
            frame_time = round(time.time() - self.start_time, 2)
        else:
            frame_time = round(float(frame_time), 2)

        now_m = time.monotonic()
        if now_m < self._low_light_cooldown_until:
            return False

        if not self.light_detector.has_sufficient_light(img):
            # Throttle dark-frame handling without blocking the recording thread (#224).
            self._low_light_cooldown_until = now_m + 1.0
            return False

        st = time.time()
        min_conf = float(app_config.get('processor.min_confidence_binary') or 0.15)
        results = self.strategy.detect(img, self.tracker, min_confidence=min_conf)
        
        if self.save_images and results:
            debug_img = img.copy()
            h, w, _ = debug_img.shape
            for res in results:
                x1, y1, x2, y2 = res.bbox
                x1, y1, x2, y2 = int(x1*w), int(y1*h), int(x2*w), int(y2*h)
                cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(debug_img, f"{res.class_name} {res.confidence:.2f}", (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.imwrite(f'data/test/frame{str(self.cnt)}.jpg', debug_img)

        if not results:
            if self.cnt <= 3 or self.cnt % 30 == 0:
                self.logger.debug(f'No detections (frame {self.cnt})')
            return False

        for res in results:
            self.update_track(res.track_id, res.class_name, res.confidence, res.bbox, frame_time, res.crop, res.blur_variance)

        self.logger.debug(
            f'Detection Time: {(time.time() - st) * 1000:.0f} msec | '
            f'Valid: {len(results)}'
        )

        return len(results) > 0

    def update_track(self, track_id, class_name, confidence, bbox, frame_time, crop=None, blur_variance=None):
        if track_id not in self.tracks:
            self.tracks[track_id] = {
                'start_time': frame_time,
                'preds': [],
                'best_frame': None,
                'best_frame_score': 0.0,
                'frames': []
            }
        if class_name is not None:
            self.tracks[track_id]['preds'].append((class_name, confidence))
        self.tracks[track_id]['end_time'] = frame_time
        
        self.tracks[track_id]['frames'].append({
            't': frame_time,
            'bbox': [round(float(b), 2) for b in bbox]
        })
        
        if crop is not None:
            if blur_variance is not None:
                pixel_count = crop.shape[0] * crop.shape[1]
                frame_score = 1.5 * math.log(blur_variance + 1) + math.log(pixel_count + 1)
                if frame_score > self.tracks[track_id]['best_frame_score']:
                    self.tracks[track_id]['best_frame'] = crop
                    self.tracks[track_id]['best_frame_score'] = frame_score
            elif self.tracks[track_id]['best_frame'] is None:
                self.tracks[track_id]['best_frame'] = crop

    def reset(self):
        self.tracks = {}
        if self.strategy:
            self.strategy.reset()
        self.start_time = time.time()
        self.cnt = 0
        self._low_light_cooldown_until = 0.0
