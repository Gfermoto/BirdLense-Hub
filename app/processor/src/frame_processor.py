import time
import math
import logging
import cv2
from frame_context import FrameContext, RoiRef
from light_level_detector import LightLevelDetector
from interfaces import DetectionStrategyProtocol
from app_config.app_config import app_config
from processor_runtime_profile import light_gate_allows_frame, resolve_runtime_profile
from processor_runtime_stats import inc_counter, observe_timing, set_gauge
from tracker_paths import resolve_tracker_config_path
from motion_detectors.opencv_live_overlay import detection_results_to_detector_polygons


class _LightGateDisabled:
    """Пропуск всех кадров в YOLO (если processor.light_gate_enabled: false)."""

    __slots__ = ()

    def has_sufficient_light(self, frame):
        return True

    def measure(self, frame):
        return {
            "brightness": None,
            "contrast": None,
            "has_sufficient_light": True,
        }


class FrameProcessor:
    def __init__(
        self,
        detection_strategy: DetectionStrategyProtocol,
        save_images=False,
        tracker="bytetrack.yaml",
    ):
        self.save_images = save_images
        self.tracker_raw = tracker
        self.tracker = resolve_tracker_config_path(tracker)
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

        self.logger.info(
            "FrameProcessor initialized (tracker=%s -> %s).",
            self.tracker_raw,
            self.tracker,
        )
        self._session_context: dict = {}
        self.reset()

    def set_session_context(self, context: dict | None) -> None:
        self._session_context = dict(context or {})

    def _frame_light_metrics(self, img):
        """Яркость/контраст + флаг light detector (для gate и для adaptive profile)."""
        if hasattr(self.light_detector, "measure"):
            metrics = dict(self.light_detector.measure(img) or {})
        else:
            metrics = {}
        if "has_sufficient_light" not in metrics:
            metrics["has_sufficient_light"] = self.light_detector.has_sufficient_light(img)
        return metrics

    def _resolve_tracker_for_profile(self, profile_name: str | None) -> str:
        """Pick tracker YAML: only ``night`` reads ``processor.tracker_profiles``; else ``processor.tracker``."""
        base = str(self.tracker or "bytetrack.yaml").strip() or "bytetrack.yaml"
        profile = str(profile_name or "").strip().lower()
        if not profile:
            return base
        profiles = app_config.get("processor.tracker_profiles") or {}
        if not isinstance(profiles, dict):
            return base
        val = profiles.get(profile)
        if val is None:
            return base
        out = str(val).strip()
        return resolve_tracker_config_path(out or base)

    def _resolve_tracker_for_fps(self, fallback_tracker: str) -> str:
        """Optional tracker override by effective stream FPS buckets."""
        raw = app_config.get("processor.tracker_fps_profiles") or {}
        if not isinstance(raw, dict):
            return fallback_tracker
        try:
            fps = float((self._session_context or {}).get("stream_fps") or 0.0)
        except (TypeError, ValueError):
            fps = 0.0
        if fps <= 0:
            return fallback_tracker
        # First matching bucket wins.
        for key in ("lte_5", "lte_7", "lte_10", "lte_15", "gt_15"):
            tracker_name = str(raw.get(key) or "").strip()
            if not tracker_name:
                continue
            if key == "lte_5" and fps <= 5.0:
                return resolve_tracker_config_path(tracker_name)
            if key == "lte_7" and fps <= 7.0:
                return resolve_tracker_config_path(tracker_name)
            if key == "lte_10" and fps <= 10.0:
                return resolve_tracker_config_path(tracker_name)
            if key == "lte_15" and fps <= 15.0:
                return resolve_tracker_config_path(tracker_name)
            if key == "gt_15" and fps > 15.0:
                return resolve_tracker_config_path(tracker_name)
        return fallback_tracker

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
        del key_frames[self.key_frame_limit:]

    def run(
        self,
        img,
        frame_time=None,
        *,
        skip_light_gate: bool = False,
        classification_frame=None,
        camera_overrides: dict | None = None,
    ):
        """
        Process frame. frame_time: optional seconds (for video file); else uses elapsed real time.

        skip_light_gate: для offline track regen по mp4 — не отсекать ночные кадры до YOLO
        (Frigate уже записал клип; иначе весь ролик может пройти без detect()).
        Adaptive profile (ночные overrides min_box_size_px, min_center_dist и т.д.) считается
        всегда; при skip только отключена проверка light_gate_allows_frame.
        """
        self.last_run_stats = {
            "yolo_ran": False,
            "yolo_track_found": False,
            "light_gate_blocked": False,
            "result_count": 0,
            "runtime_profile": None,
            "profile_overrides": {},
        }
        if img is None:
            raise Exception("Frame is missing")
        self.cnt += 1

        if frame_time is None:
            frame_time = round(time.time() - self.start_time, 2)
        else:
            frame_time = round(float(frame_time), 2)

        self.last_frame_context = FrameContext(
            frame_index=self.cnt,
            frame_time=frame_time,
            runtime_profile=None,
            light_brightness=None,
            light_contrast=None,
        )

        metrics = self._frame_light_metrics(img)
        profile_name, profile_overrides = resolve_runtime_profile(
            app_config,
            brightness=metrics.get("brightness"),
            contrast=metrics.get("contrast"),
        )
        profile_overrides = dict(profile_overrides or {})
        # Camera-specific tuning (e.g. distant camera with smaller birds) overlays
        # profile values and applies even outside night profile.
        if isinstance(camera_overrides, dict) and camera_overrides:
            profile_overrides.update(camera_overrides)
        if getattr(self.strategy, "_for_track_regen", False):
            raw_mc = app_config.get("processor.track_regen_min_confidence_binary")
            if raw_mc is not None:
                try:
                    profile_overrides["min_confidence_binary"] = float(raw_mc)
                except (TypeError, ValueError):
                    pass
            raw_bird = app_config.get("processor.track_regen_min_confidence_binary_bird")
            if raw_bird is not None:
                try:
                    profile_overrides["min_confidence_binary_bird"] = float(raw_bird)
                except (TypeError, ValueError):
                    pass
        self.last_run_stats["runtime_profile"] = profile_name
        self.last_run_stats["profile_overrides"] = dict(profile_overrides)
        self.last_run_stats["light_brightness"] = metrics.get("brightness")
        self.last_run_stats["light_contrast"] = metrics.get("contrast")
        self.last_frame_context.runtime_profile = profile_name
        self.last_frame_context.light_brightness = metrics.get("brightness")
        self.last_frame_context.light_contrast = metrics.get("contrast")
        set_gauge("last_runtime_profile", profile_name or "none")
        if metrics.get("brightness") is not None:
            set_gauge("light_brightness", round(float(metrics["brightness"]), 3))
        if metrics.get("contrast") is not None:
            set_gauge("light_contrast", round(float(metrics["contrast"]), 3))

        if not skip_light_gate:
            now_m = time.monotonic()
            if now_m < self._low_light_cooldown_until:
                self.last_run_stats["light_gate_blocked"] = True
                self.live_detector_polygons = []
                return False

            if not light_gate_allows_frame(
                brightness=metrics.get("brightness"),
                contrast=metrics.get("contrast"),
                base_has_sufficient_light=bool(metrics.get("has_sufficient_light")),
                profile_overrides=profile_overrides,
            ):
                # Throttle dark-frame handling without blocking the recording thread (#224).
                self._low_light_cooldown_until = now_m + 1.0
                self.last_run_stats["light_gate_blocked"] = True
                self.live_detector_polygons = []
                return False

        st = time.time()
        try:
            min_conf = float(
                profile_overrides.get("min_confidence_binary", app_config.get("processor.min_confidence_binary"))
            )
        except (TypeError, ValueError):
            min_conf = 0.22
        auto_unstick_enabled = bool(app_config.get("processor.auto_unstick_enabled", True))
        try:
            auto_unstick_no_track_frames = int(app_config.get("processor.auto_unstick_no_track_frames") or 180)
        except (TypeError, ValueError):
            auto_unstick_no_track_frames = 180
        try:
            auto_unstick_min_conf = float(app_config.get("processor.auto_unstick_min_confidence_binary") or 0.12)
        except (TypeError, ValueError):
            auto_unstick_min_conf = 0.12
        try:
            auto_unstick_min_conf_bird = float(
                app_config.get("processor.auto_unstick_min_confidence_binary_bird") or auto_unstick_min_conf
            )
        except (TypeError, ValueError):
            auto_unstick_min_conf_bird = auto_unstick_min_conf
        try:
            auto_unstick_min_box_px = int(app_config.get("processor.auto_unstick_min_box_size_px") or 12)
        except (TypeError, ValueError):
            auto_unstick_min_box_px = 12
        try:
            auto_unstick_min_center_dist = float(app_config.get("processor.auto_unstick_min_center_dist") or 0.0)
        except (TypeError, ValueError):
            auto_unstick_min_center_dist = 0.0
        if (
            auto_unstick_enabled
            and auto_unstick_no_track_frames > 0
            and self._consecutive_no_track_frames >= auto_unstick_no_track_frames
        ):
            min_conf = min(min_conf, auto_unstick_min_conf)
            try:
                curr_bird = profile_overrides.get("min_confidence_binary_bird")
                if curr_bird is None:
                    curr_bird = app_config.get("processor.min_confidence_binary_bird")
                curr_bird_f = float(curr_bird) if curr_bird is not None else auto_unstick_min_conf_bird
                profile_overrides["min_confidence_binary_bird"] = min(curr_bird_f, auto_unstick_min_conf_bird)
            except (TypeError, ValueError):
                profile_overrides["min_confidence_binary_bird"] = auto_unstick_min_conf_bird
            try:
                curr_box = profile_overrides.get("min_box_size_px")
                if curr_box is None:
                    curr_box = app_config.get("processor.min_box_size_px")
                curr_box_i = int(curr_box) if curr_box is not None else auto_unstick_min_box_px
                profile_overrides["min_box_size_px"] = min(curr_box_i, auto_unstick_min_box_px)
            except (TypeError, ValueError):
                profile_overrides["min_box_size_px"] = auto_unstick_min_box_px
            try:
                curr_center = profile_overrides.get("min_center_dist")
                if curr_center is None:
                    curr_center = app_config.get("processor.min_center_dist")
                curr_center_f = float(curr_center) if curr_center is not None else auto_unstick_min_center_dist
                profile_overrides["min_center_dist"] = min(curr_center_f, auto_unstick_min_center_dist)
            except (TypeError, ValueError):
                profile_overrides["min_center_dist"] = auto_unstick_min_center_dist
            self.last_run_stats["auto_unstick_active"] = True
        else:
            self.last_run_stats["auto_unstick_active"] = False
        tracker_cfg = self._resolve_tracker_for_profile(self.last_run_stats.get("runtime_profile"))
        if self.last_run_stats.get("auto_unstick_active"):
            # Universal fallback tracker profile for weak/small distant objects.
            profile = str(self.last_run_stats.get("runtime_profile") or "").strip().lower()
            if profile == "night":
                unstick_tracker = str(app_config.get("processor.auto_unstick_tracker_night") or "").strip()
            else:
                unstick_tracker = str(app_config.get("processor.auto_unstick_tracker") or "").strip()
            if unstick_tracker:
                tracker_cfg = resolve_tracker_config_path(unstick_tracker)
                self.last_run_stats["auto_unstick_tracker_used"] = tracker_cfg
        if isinstance(camera_overrides, dict):
            tracker_override = str(camera_overrides.get("tracker") or "").strip()
            if tracker_override:
                tracker_cfg = resolve_tracker_config_path(tracker_override)
        tracker_cfg = self._resolve_tracker_for_fps(tracker_cfg)
        self.last_run_stats["tracker_used"] = tracker_cfg
        set_gauge("tracker_config_used", tracker_cfg)
        self.last_run_stats["yolo_ran"] = True
        self.last_frame_context.yolo_ran = True
        results = self.strategy.detect(
            img,
            tracker_cfg,
            min_confidence=min_conf,
            profile_overrides=profile_overrides,
            classification_frame=classification_frame,
        )
        detect_ms = (time.time() - st) * 1000.0
        observe_timing("frame_processor_detect", detect_ms)
        try:
            warn_ms = float(app_config.get("processor.frame_processing_warn_ms") or 0.0)
        except (TypeError, ValueError):
            warn_ms = 0.0
        if warn_ms > 0 and detect_ms >= warn_ms:
            inc_counter("slow_frame_processor_detect_total")
            self.logger.warning("Slow frame processing: %.1fms >= %.1fms", detect_ms, warn_ms)
        self.last_run_stats["result_count"] = len(results or [])
        dm = getattr(self.strategy, "last_detect_metrics", None) or {}
        self.last_run_stats["yolo_raw_boxes"] = int(dm.get("raw_boxes") or 0)
        self.last_run_stats["yolo_boxes_with_track_id"] = int(dm.get("boxes_with_track_id") or 0)
        self.last_run_stats["yolo_accepted_boxes"] = int(dm.get("accepted") or 0)
        self.last_frame_context.yolo_raw_boxes = self.last_run_stats["yolo_raw_boxes"]
        self.last_frame_context.yolo_accepted_boxes = self.last_run_stats["yolo_accepted_boxes"]
        self.last_frame_context.tracker_used = tracker_cfg
        self.last_run_stats["yolo_predict_fallback"] = bool(dm.get("predict_fallback"))
        self.last_run_stats["frame_copy_count_per_frame"] = int(
            dm.get("frame_copy_count_per_frame") or 0
        )
        set_gauge(
            "frame_copy_count_per_frame",
            self.last_run_stats["frame_copy_count_per_frame"],
        )
        self.last_run_stats["yolo_track_found"] = bool(results)
        if self.last_run_stats["yolo_track_found"]:
            self._consecutive_no_track_frames = 0
        else:
            self._consecutive_no_track_frames += 1
        current_track_ids = {int(res.track_id) for res in (results or []) if int(getattr(res, "track_id", 0) or 0) > 0}
        if self._previous_track_ids and current_track_ids and self._previous_track_ids.isdisjoint(current_track_ids):
            self._id_switch_events += 1
        self._previous_track_ids = set(current_track_ids)
        self._frames_observed_for_tracking += 1
        if current_track_ids:
            self._frames_with_tracks += 1
        lifetimes = []
        static_like = 0
        total_tracks = 0
        for tr in self.tracks.values():
            frames = tr.get("frames") if isinstance(tr.get("frames"), list) else []
            if len(frames) < 2:
                continue
            total_tracks += 1
            lifetimes.append(len(frames))
            first_bbox = frames[0].get("bbox") if isinstance(frames[0], dict) else None
            last_bbox = frames[-1].get("bbox") if isinstance(frames[-1], dict) else None
            if isinstance(first_bbox, list) and isinstance(last_bbox, list) and len(first_bbox) == 4 and len(last_bbox) == 4:
                c1x = (float(first_bbox[0]) + float(first_bbox[2])) * 0.5
                c1y = (float(first_bbox[1]) + float(first_bbox[3])) * 0.5
                c2x = (float(last_bbox[0]) + float(last_bbox[2])) * 0.5
                c2y = (float(last_bbox[1]) + float(last_bbox[3])) * 0.5
                if math.hypot(c2x - c1x, c2y - c1y) < 0.02:
                    static_like += 1
        avg_lifetime = (sum(lifetimes) / len(lifetimes)) if lifetimes else 0.0
        id_switch_rate = float(self._id_switch_events) / float(max(1, self._frames_with_tracks))
        static_box_ratio = float(static_like) / float(max(1, total_tracks))
        self.last_run_stats["avg_track_lifetime_frames"] = round(avg_lifetime, 3)
        self.last_run_stats["id_switch_rate"] = round(id_switch_rate, 6)
        self.last_run_stats["static_box_ratio"] = round(static_box_ratio, 6)
        set_gauge("avg_track_lifetime_frames", self.last_run_stats["avg_track_lifetime_frames"])
        set_gauge("id_switch_rate", self.last_run_stats["id_switch_rate"])
        set_gauge("static_box_ratio", self.last_run_stats["static_box_ratio"])

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

        self.live_detector_polygons = detection_results_to_detector_polygons(results)
        if not results:
            if self.cnt <= 3 or self.cnt % 30 == 0:
                self.logger.debug(f"No detections (frame {self.cnt})")
            return False

        for res in results:
            self.last_frame_context.roi_refs.append(
                RoiRef(
                    track_id=int(res.track_id),
                    bbox_norm=tuple(float(b) for b in res.bbox),
                    source_shape=(int(img.shape[0]), int(img.shape[1])),
                )
            )
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
                classifier_entropy=getattr(res, "classifier_entropy", None),
                classifier_top1_top2_margin=getattr(res, "classifier_top1_top2_margin", None),
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
        *,
        classifier_entropy=None,
        classifier_top1_top2_margin=None,
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
            ev = {
                "species_name": class_name,
                "confidence": float(classifier_confidence or 0.0),
                "detector_confidence": float(detector_confidence or 0.0),
                "combined_confidence": combined_conf,
                "t": frame_time,
            }
            if classifier_entropy is not None:
                ev["entropy"] = float(classifier_entropy)
            if classifier_top1_top2_margin is not None:
                ev["top1_top2_margin"] = float(classifier_top1_top2_margin)
            self.tracks[track_id]["classifier_events"].append(ev)
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
        self._consecutive_no_track_frames = 0
        self.last_frame_context = None
        self._frames_observed_for_tracking = 0
        self._frames_with_tracks = 0
        self._id_switch_events = 0
        self._previous_track_ids = set()
        self.live_detector_polygons = []
