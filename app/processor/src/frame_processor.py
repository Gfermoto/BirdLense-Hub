import time
import math
import logging
import cv2
from light_level_detector import LightLevelDetector
from interfaces import DetectionStrategyProtocol
from app_config.app_config import app_config


class _LightGateDisabled:
    """Пропуск всех кадров в YOLO (если processor.light_gate_enabled: false)."""

    __slots__ = ()

    def has_sufficient_light(self, frame):
        return True


class FrameProcessor:
    def __init__(
        self,
        detection_strategy: DetectionStrategyProtocol,
        save_images=False,
        tracker="bytetrack.yaml",
    ):
        self.save_images = save_images
        self.tracker = tracker
        self.logger = logging.getLogger(__name__)
        if bool(app_config.get("processor.light_gate_enabled", True)):
            mb = int(app_config.get("processor.light_gate_min_brightness") or 25)
            mc = int(app_config.get("processor.light_gate_min_contrast") or 20)
            self.light_detector = LightLevelDetector(
                min_brightness=max(0, min(mb, 255)),
                min_contrast=max(0, min(mc, 255)),
            )
        else:
            self.light_detector = _LightGateDisabled()

        self.strategy = detection_strategy
        try:
            self.key_frame_limit = max(1, int(app_config.get("processor.key_frame_limit") or 3))
        except (TypeError, ValueError):
            self.key_frame_limit = 3

        self.logger.info("FrameProcessor initialized.")
        self.reset()

    def _update_key_frames(self, track: dict, crop, frame_time, bbox, frame_score):
        key_frames = track.setdefault("key_frames", [])
        entry = {
            "crop": crop,
            "score": float(frame_score),
            "t": frame_time,
            "bbox": [round(float(b), 4) for b in bbox],
        }
        key_frames.append(entry)
        key_frames.sort(key=lambda item: item["score"], reverse=True)
        del key_frames[self.key_frame_limit :]

    def run(self, img, frame_time=None, *, skip_light_gate: bool = False):
        """
        Process frame. frame_time: optional seconds (for video file); else uses elapsed real time.

        skip_light_gate: для offline track regen по mp4 — не отсекать ночные кадры до YOLO
        (Frigate уже записал клип; иначе весь ролик может пройти без detect()).
        """
        self.last_run_stats = {
            "yolo_ran": False,
            "yolo_track_found": False,
            "light_gate_blocked": False,
            "result_count": 0,
        }
        if img is None:
            raise Exception("Frame is missing")
        self.cnt += 1

        if frame_time is None:
            frame_time = round(time.time() - self.start_time, 2)
        else:
            frame_time = round(float(frame_time), 2)

        if not skip_light_gate:
            now_m = time.monotonic()
            if now_m < self._low_light_cooldown_until:
                # Не крутить CPU в tight-loop пока действует cooldown (#237 review).
                time.sleep(min(0.02, self._low_light_cooldown_until - now_m))
                self.last_run_stats["light_gate_blocked"] = True
                return False

            if not self.light_detector.has_sufficient_light(img):
                # Throttle dark-frame handling without blocking the recording thread (#224).
                self._low_light_cooldown_until = now_m + 1.0
                time.sleep(0.02)
                self.last_run_stats["light_gate_blocked"] = True
                return False

        st = time.time()
        min_conf = float(app_config.get("processor.min_confidence_binary") or 0.22)
        self.last_run_stats["yolo_ran"] = True
        results = self.strategy.detect(img, self.tracker, min_confidence=min_conf)
        self.last_run_stats["result_count"] = len(results or [])
        self.last_run_stats["yolo_track_found"] = bool(results)

        if self.save_images and results:
            debug_img = img.copy()
            h, w, _ = debug_img.shape
            for res in results:
                x1, y1, x2, y2 = res.bbox
                x1, y1, x2, y2 = int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
                cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = res.class_name or res.detector_label or "Bird"
                cv2.putText(
                    debug_img,
                    f"{label} {res.confidence:.2f}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )
            cv2.imwrite(f"data/test/frame{str(self.cnt)}.jpg", debug_img)

        if not results:
            if self.cnt <= 3 or self.cnt % 30 == 0:
                self.logger.debug(f"No detections (frame {self.cnt})")
            return False

        for res in results:
            self.update_track(
                res.track_id,
                res.detector_label,
                res.class_name,
                res.detector_confidence,
                res.classifier_confidence,
                res.bbox,
                frame_time,
                res.crop,
                res.blur_variance,
            )

        self.logger.debug(f"Detection Time: {(time.time() - st) * 1000:.0f} msec | Valid: {len(results)}")

        return len(results) > 0

    def update_track(
        self,
        track_id,
        detector_label,
        class_name,
        detector_confidence,
        classifier_confidence,
        bbox,
        frame_time,
        crop=None,
        blur_variance=None,
    ):
        if track_id not in self.tracks:
            self.tracks[track_id] = {
                "start_time": frame_time,
                "detector_events": [],
                "classifier_events": [],
                "best_frame": None,
                "best_frame_score": 0.0,
                "frames": [],
                "key_frames": [],
            }
        self.tracks[track_id]["detector_events"].append(
            {
                "label": detector_label,
                "confidence": float(detector_confidence or 0.0),
                "t": frame_time,
            }
        )
        if class_name is not None and classifier_confidence is not None:
            combined_conf = float(detector_confidence or 0.0) * float(classifier_confidence or 0.0)
            self.tracks[track_id]["classifier_events"].append(
                {
                    "species_name": class_name,
                    "confidence": float(classifier_confidence or 0.0),
                    "detector_confidence": float(detector_confidence or 0.0),
                    "combined_confidence": combined_conf,
                    "t": frame_time,
                }
            )
        self.tracks[track_id]["end_time"] = frame_time

        self.tracks[track_id]["frames"].append({"t": frame_time, "bbox": [round(float(b), 4) for b in bbox]})

        if crop is not None:
            if blur_variance is not None:
                pixel_count = crop.shape[0] * crop.shape[1]
                frame_score = 1.5 * math.log(blur_variance + 1) + math.log(pixel_count + 1)
                self._update_key_frames(self.tracks[track_id], crop, frame_time, bbox, frame_score)
                if frame_score > self.tracks[track_id]["best_frame_score"]:
                    self.tracks[track_id]["best_frame"] = crop
                    self.tracks[track_id]["best_frame_score"] = frame_score
            elif self.tracks[track_id]["best_frame"] is None:
                self.tracks[track_id]["best_frame"] = crop
                self._update_key_frames(self.tracks[track_id], crop, frame_time, bbox, 0.0)

    def reset(self):
        self.tracks = {}
        if self.strategy:
            self.strategy.reset()
        self.start_time = time.time()
        self.cnt = 0
        self._low_light_cooldown_until = 0.0
        self.last_run_stats = {
            "yolo_ran": False,
            "yolo_track_found": False,
            "light_gate_blocked": False,
            "result_count": 0,
        }
