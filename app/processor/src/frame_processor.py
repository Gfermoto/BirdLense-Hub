import time
import math
import logging
import cv2
from frame_context import FrameContext, RoiRef
from light_level_detector import LightLevelDetector
from interfaces import DetectionStrategyProtocol
from app_config.app_config import app_config
from processor_runtime_profile import light_gate_allows_frame, resolve_runtime_profile
from threshold_resolution import merge_adaptive_profile_overrides
from processor_runtime_stats import inc_counter, observe_timing, set_gauge
from tracker_paths import resolve_tracker_config_path
from tracker_low_fps import resolve_adaptive_tracker_path
from track_stability import TrackStabilityMonitor, summarize_tracks_stability
from motion_detectors.opencv_live_overlay import (
    detection_results_to_detector_polygons,
    tracks_to_detector_polygons,
)
from roi_crop import crop_for_classifier
from processor_config_defaults import (
    AUTO_UNSTICK_MIN_BOX_SIZE_PX,
    AUTO_UNSTICK_MIN_CENTER_DIST,
    AUTO_UNSTICK_MIN_CONFIDENCE_BINARY,
    AUTO_UNSTICK_MIN_CONFIDENCE_BINARY_BIRD,
    AUTO_UNSTICK_NO_TRACK_FRAMES,
    MIN_CONFIDENCE_BINARY,
    config_float,
    config_int,
)


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
        try:
            iou_thr = float(app_config.get("processor.track_id_switch_iou_threshold") or 0.25)
        except (TypeError, ValueError):
            iou_thr = 0.25
        self._stability_monitor = TrackStabilityMonitor(iou_threshold=iou_thr)
        self._last_live_polygons: list = []
        self._last_live_polygons_at = 0.0
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
        picked = fallback_tracker
        try:
            fps = float((self._session_context or {}).get("stream_fps") or 0.0)
        except (TypeError, ValueError):
            fps = 0.0
        if isinstance(raw, dict) and fps > 0:
            for key in ("lte_5", "lte_7", "lte_10", "lte_15", "gt_15"):
                tracker_name = str(raw.get(key) or "").strip()
                if not tracker_name:
                    continue
                if key == "lte_5" and fps <= 5.0:
                    picked = resolve_tracker_config_path(tracker_name)
                    break
                if key == "lte_7" and fps <= 7.0:
                    picked = resolve_tracker_config_path(tracker_name)
                    break
                if key == "lte_10" and fps <= 10.0:
                    picked = resolve_tracker_config_path(tracker_name)
                    break
                if key == "lte_15" and fps <= 15.0:
                    picked = resolve_tracker_config_path(tracker_name)
                    break
                if key == "gt_15" and fps > 15.0:
                    picked = resolve_tracker_config_path(tracker_name)
                    break
        return resolve_adaptive_tracker_path(picked, fps)

    def get_tracking_stability_stats(self) -> dict:
        try:
            fps = float((self._session_context or {}).get("stream_fps") or 0.0)
        except (TypeError, ValueError):
            fps = 0.0
        out = summarize_tracks_stability(
            self.tracks,
            stream_fps=fps,
            id_switches_increment=int(self._stability_monitor.track_id_switches_count),
        )
        out["id_switch_rate"] = self.last_run_stats.get("id_switch_rate", 0.0)
        return out

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

    def _overlay_tracks_for_live(self, frame_time: float) -> dict:
        try:
            max_age_sec = float(app_config.get("ui.live_overlay_track_ttl_seconds") or 0.6)
        except (TypeError, ValueError):
            max_age_sec = 0.6
        max_age_sec = min(2.0, max(0.1, max_age_sec))
        out: dict = {}
        for track_id, track in self.tracks.items():
            if not isinstance(track, dict):
                continue
            end_time = track.get("end_time")
            try:
                age = float(frame_time) - float(end_time)
            except (TypeError, ValueError):
                continue
            if age <= max_age_sec:
                out[track_id] = track
        return out

    def _live_overlay_max_age_sec(self) -> float:
        try:
            max_age_sec = float(app_config.get("ui.live_overlay_track_ttl_seconds") or 0.6)
        except (TypeError, ValueError):
            max_age_sec = 0.6
        return min(2.0, max(0.1, max_age_sec))

    def _refresh_live_detector_polygons(self, frame_time: float, results=None) -> None:
        """Live green boxes during recording: prefer track history, else last frame detections."""
        max_age = self._live_overlay_max_age_sec()
        ft = float(frame_time)
        if results:
            current = detection_results_to_detector_polygons(results)
            if current:
                self._last_live_polygons = current
                self._last_live_polygons_at = ft
        track_polys = tracks_to_detector_polygons(self._overlay_tracks_for_live(ft))
        if track_polys:
            self.live_detector_polygons = track_polys
            return
        if self._last_live_polygons and (ft - self._last_live_polygons_at) <= max_age:
            self.live_detector_polygons = list(self._last_live_polygons)
            return
        self.live_detector_polygons = []

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
        profile_name, adaptive_overrides = resolve_runtime_profile(
            app_config,
            brightness=metrics.get("brightness"),
            contrast=metrics.get("contrast"),
        )
        profile_overrides = merge_adaptive_profile_overrides(
            dict(camera_overrides or {}),
            adaptive_overrides,
        )
        policy = getattr(self, "tracking_policy", None) or getattr(self.strategy, "_tracking_policy", None)
        if policy is not None and not policy.unified_with_live and policy.for_track_regen:
            from tracking_policy import apply_policy_profile_overrides

            profile_overrides = apply_policy_profile_overrides(profile_overrides, policy)
        elif getattr(self.strategy, "_for_track_regen", False):
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
            min_conf = config_float(
                app_config,
                "processor.min_confidence_binary",
                MIN_CONFIDENCE_BINARY,
            )
            if profile_overrides.get("min_confidence_binary") is not None:
                min_conf = float(profile_overrides["min_confidence_binary"])
        except (TypeError, ValueError):
            min_conf = MIN_CONFIDENCE_BINARY
        auto_unstick_enabled = bool(app_config.get("processor.auto_unstick_enabled", True))
        auto_unstick_no_track_frames = config_int(
            app_config,
            "processor.auto_unstick_no_track_frames",
            AUTO_UNSTICK_NO_TRACK_FRAMES,
        )
        auto_unstick_min_conf = config_float(
            app_config,
            "processor.auto_unstick_min_confidence_binary",
            AUTO_UNSTICK_MIN_CONFIDENCE_BINARY,
        )
        auto_unstick_min_conf_bird = config_float(
            app_config,
            "processor.auto_unstick_min_confidence_binary_bird",
            AUTO_UNSTICK_MIN_CONFIDENCE_BINARY_BIRD,
        )
        auto_unstick_min_box_px = config_int(
            app_config,
            "processor.auto_unstick_min_box_size_px",
            AUTO_UNSTICK_MIN_BOX_SIZE_PX,
        )
        auto_unstick_min_center_dist = config_float(
            app_config,
            "processor.auto_unstick_min_center_dist",
            AUTO_UNSTICK_MIN_CENTER_DIST,
        )
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
        _tp = getattr(self, "tracking_policy", None)
        if _tp is not None:
            tracker_cfg = _tp.resolve_tracker_path(tracker_cfg)
        else:
            tracker_cfg = self._resolve_tracker_for_fps(tracker_cfg)
        try:
            eff_fps = float((self._session_context or {}).get("stream_fps") or 0.0)
        except (TypeError, ValueError):
            eff_fps = 0.0
        self.last_run_stats["tracker_used"] = tracker_cfg
        self.last_run_stats["stream_fps"] = round(eff_fps, 3) if eff_fps > 0 else 0.0
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
        self.last_run_stats["frame_copy_count_per_frame"] = int(dm.get("frame_copy_count_per_frame") or 0)
        set_gauge(
            "frame_copy_count_per_frame",
            self.last_run_stats["frame_copy_count_per_frame"],
        )
        self.last_run_stats["yolo_track_found"] = bool(results)
        self._stability_monitor.observe_detections(results)
        stability = self.get_tracking_stability_stats()
        self.last_run_stats["track_id_switches_count"] = int(stability.get("track_id_switches_count") or 0)
        self.last_run_stats["avg_track_duration_sec"] = float(stability.get("avg_track_duration_sec") or 0.0)
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
            if (
                isinstance(first_bbox, list)
                and isinstance(last_bbox, list)
                and len(first_bbox) == 4
                and len(last_bbox) == 4
            ):
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

        if not results:
            self._refresh_live_detector_polygons(frame_time)
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
        self._refresh_live_detector_polygons(frame_time, results=results)

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
            # Zero-copy ROI path may pass RoiCropRef; convert to ndarray for scoring/keyframes.
            try:
                crop_arr, _ = crop_for_classifier(crop)
            except Exception:
                crop_arr = None
            if crop_arr is None or getattr(crop_arr, "size", 0) <= 0:
                return
            if blur_variance is not None:
                pixel_count = crop_arr.shape[0] * crop_arr.shape[1]
                frame_score = 1.5 * math.log(blur_variance + 1) + math.log(pixel_count + 1)
                self._update_key_frames(
                    self.tracks[track_id],
                    crop_arr,
                    frame_time,
                    bbox,
                    frame_score,
                )
                if frame_score > self.tracks[track_id]["best_frame_score"]:
                    self.tracks[track_id]["best_frame"] = crop_arr
                    self.tracks[track_id]["best_frame_score"] = frame_score
            elif self.tracks[track_id]["best_frame"] is None:
                self.tracks[track_id]["best_frame"] = crop_arr
                self._update_key_frames(
                    self.tracks[track_id],
                    crop_arr,
                    frame_time,
                    bbox,
                    0.0,
                )

    def confirmed_track_anchor(
        self,
        *,
        app_config,
        min_track_duration: float,
        min_confidence_to_process: float,
    ) -> dict | None:
        """Return best confirmed YOLO+ByteTrack bbox anchor, or None."""
        from linear_pipeline import evaluate_track_linear
        from track_first_contract import is_valid_norm_bbox, valid_track_frames

        best: dict | None = None
        for track_id, track in (self.tracks or {}).items():
            if not isinstance(track, dict) or not track.get("detector_events"):
                continue
            decision = evaluate_track_linear(
                app_config=app_config,
                track=track,
                min_track_duration=float(min_track_duration),
                min_confidence_to_process=float(min_confidence_to_process),
            )
            if not bool(decision.get("accepted")):
                continue
            frames = valid_track_frames(track.get("frames"))
            if not frames:
                continue
            bbox = list(frames[-1].get("bbox") or [])
            if not is_valid_norm_bbox(bbox):
                continue
            candidate = {
                "track_id": track_id,
                "bbox": bbox,
                "start_time": track.get("start_time"),
                "end_time": track.get("end_time"),
                "confidence": float(decision.get("out_conf") or decision.get("detector_conf") or 0.0),
                "detector_label": decision.get("detector_label") or "Bird",
                "detector_confidence": float(decision.get("detector_conf") or 0.0),
                "detector_event_count": int(decision.get("detector_event_count") or 0),
                "frames": frames,
                "key_frame_count": len(track.get("key_frames") or []),
            }
            if best is None or (
                float(candidate["confidence"]),
                int(candidate["detector_event_count"]),
            ) > (
                float(best["confidence"]),
                int(best["detector_event_count"]),
            ):
                best = candidate
        return best

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
        self._stability_monitor.reset()
        self.live_detector_polygons = []
        self._last_live_polygons = []
        self._last_live_polygons_at = 0.0
