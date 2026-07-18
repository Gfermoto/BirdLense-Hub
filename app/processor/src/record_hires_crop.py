"""Hi-res BGR crop from main recording MP4 (shared by TG preview, classifier, ReID)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from typing import Any, Mapping

import cv2
import numpy as np
from shared.frame_shape import numpy_hw, parse_config_wh, parse_metadata_hw, wh_to_hw

logger = logging.getLogger(__name__)

_CROP_SOURCES = frozenset({"best_frame_lores", "record_hires", "auto"})


def resolve_enrichment_crop_source(
    app_config: Mapping[str, Any] | None,
    *,
    config_key: str,
    default: str = "auto",
) -> str:
    raw = default
    if app_config is not None:
        raw = str(app_config.get(config_key) or default).strip().lower()
    if raw in _CROP_SOURCES:
        return raw
    return default


def resolve_crop_pad_frac(
    app_config: Mapping[str, Any] | None = None,
    *,
    runtime_cfg: Mapping[str, Any] | None = None,
) -> float:
    raw = 0.06
    for cfg in (runtime_cfg, app_config):
        if cfg is None:
            continue
        try:
            val = cfg.get("processor.enrichment_crop_pad_frac")
            if val is None:
                val = cfg.get("processor.notify_preview_crop_pad_frac")
            if val is not None:
                raw = float(val)
                break
        except (TypeError, ValueError):
            continue
    return max(0.0, min(0.25, raw))


def resolve_record_crop_geometry(
    detection: Mapping[str, Any],
    *,
    crop_shape_hw: tuple[int, int],
    runtime_cfg: Mapping[str, Any] | None = None,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """(detector_hw, overlay_hw, playback_hw) for hires bbox remap."""
    playback_hw = crop_shape_hw
    for key in ("playback_shape_hw", "record_shape_hw"):
        shaped = parse_metadata_hw(detection.get(key))
        if shaped is not None:
            playback_hw = shaped
            break

    overlay_hw = playback_hw
    for key in ("overlay_shape_hw", "detect_shape_hw"):
        shaped = parse_metadata_hw(detection.get(key))
        if shaped is not None:
            overlay_hw = shaped
            break
    if overlay_hw == playback_hw and runtime_cfg is not None:
        lores_wh = parse_config_wh(runtime_cfg.get("processor.inference_lores_wh"))
        if lores_wh is not None:
            overlay_hw = wh_to_hw(lores_wh)

    detector_hw = overlay_hw
    shaped = parse_metadata_hw(detection.get("detector_shape_hw"))
    if shaped is not None:
        detector_hw = shaped

    return detector_hw, overlay_hw, playback_hw


def _bbox_stored_in_playback_space(
    detection: Mapping[str, Any],
    *,
    crop_shape_hw: tuple[int, int],
) -> bool:
    """Persisted track frames use playback-normalized xyxy when metadata matches MP4."""
    for key in ("playback_shape_hw", "record_shape_hw"):
        playback_hw = parse_metadata_hw(detection.get(key))
        if playback_hw is not None:
            return playback_hw == crop_shape_hw
    return False


def remap_bbox_for_record_crop(
    bbox: list[float],
    detection: Mapping[str, Any],
    *,
    crop_shape_hw: tuple[int, int],
    runtime_cfg: Mapping[str, Any] | None = None,
) -> list[float] | None:
    """Map norm bbox onto main MP4 crop frame (legacy rows only)."""
    if _bbox_stored_in_playback_space(detection, crop_shape_hw=crop_shape_hw):
        return [float(v) for v in bbox]

    from frame_geometry import remap_norm_bbox_for_crop

    det_hw, overlay_hw, playback_hw = resolve_record_crop_geometry(
        detection,
        crop_shape_hw=crop_shape_hw,
        runtime_cfg=runtime_cfg,
    )
    if overlay_hw == crop_shape_hw and det_hw == overlay_hw:
        return bbox
    mapped = remap_norm_bbox_for_crop(
        bbox,
        detector_shape_hw=det_hw,
        overlay_shape_hw=overlay_hw,
        crop_shape_hw=crop_shape_hw,
        playback_shape_hw=playback_hw,
    )
    if mapped is None:
        return None
    return [float(v) for v in mapped]


def enrichment_crop_require_best_keyframe(runtime_cfg: Mapping[str, Any] | None) -> bool:
    """Linear default: crop/TG seek only from scored keyframe, not blind mid-track frame."""
    if runtime_cfg is None:
        return False
    raw = runtime_cfg.get("processor.enrichment_crop_require_keyframe")
    if raw is not None:
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw)
    return str(runtime_cfg.get("processor.pipeline_mode") or "").strip().lower() == "linear"


def pick_bbox_and_timestamp(
    detection: Mapping[str, Any],
    *,
    runtime_cfg: Mapping[str, Any] | None = None,
    require_best_keyframe: bool | None = None,
) -> tuple[list[float] | None, float]:
    """Normalized bbox + record-timeline seconds (same rules as notify preview)."""
    if require_best_keyframe is None:
        require_best_keyframe = enrichment_crop_require_best_keyframe(runtime_cfg)

    def _pick_timestamp() -> float:
        try:
            st = float(detection.get("start_time") or 0)
            et = float(detection.get("end_time") or st)
            t_mid = st + (et - st) * 0.5 if et > st else st
        except Exception:
            t_mid = 0.0
        return _apply_record_offset(float(t_mid))

    def _apply_record_offset(ts: float) -> float:
        if detection.get("playback_timeline_synced"):
            return max(0.0, float(ts))
        try:
            from dual_stream_timeline import (
                apply_record_time_offset,
                resolve_detect_record_time_offset_sec,
            )

            cam = str(detection.get("camera_id") or detection.get("triggered_camera") or "").strip()
            offset = resolve_detect_record_time_offset_sec(runtime_cfg, camera_id=cam or None)
            return apply_record_time_offset(float(ts), offset)
        except ImportError:
            return float(ts)

    key_frames = detection.get("key_frames") or []
    best_kf = None
    if isinstance(key_frames, list) and key_frames:
        dict_frames = [kf for kf in key_frames if isinstance(kf, dict)]
        if dict_frames:
            best_kf = max(dict_frames, key=lambda k: float(k.get("score") or 0.0))

    if best_kf is not None:
        bb = best_kf.get("bbox")
        bbox = None
        if isinstance(bb, (list, tuple)) and len(bb) == 4:
            try:
                bbox = [float(v) for v in bb]
            except (TypeError, ValueError):
                bbox = None
        t = _apply_record_offset(float(best_kf.get("t") or _pick_timestamp()))
        if bbox is not None:
            return bbox, float(t)
        if require_best_keyframe and isinstance(key_frames, list) and key_frames:
            return None, float(t)

    # key_frames may be stripped from notify payload (key_frame_count only); use frames.
    if require_best_keyframe and isinstance(key_frames, list) and key_frames:
        return None, float(_pick_timestamp())

    frames = detection.get("frames") or []
    mid = frames[len(frames) // 2] if isinstance(frames, list) and frames else None
    bbox = mid.get("bbox") if isinstance(mid, dict) else None
    if isinstance(mid, dict):
        t = _apply_record_offset(float(mid.get("t") or _pick_timestamp()))
    else:
        t = _pick_timestamp()
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            bbox = [float(v) for v in bbox]
        except (TypeError, ValueError):
            bbox = None
    else:
        bbox = None
    return bbox, float(t)


def _ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def _read_frame_ffmpeg(
    video_path: str,
    ts: float,
    *,
    hwaccel: bool,
    deadline_mono: float | None = None,
) -> np.ndarray | None:
    """Extract one frame via ffmpeg (optional CUDA). Spawn cost is high — last-resort fallback."""
    ff = _ffmpeg_bin()
    if not ff:
        return None
    if deadline_mono is not None and time.perf_counter() >= deadline_mono:
        return None
    cmd: list[str] = [ff, "-hide_banner", "-loglevel", "error"]
    if hwaccel:
        cmd += ["-hwaccel", "cuda"]
    cmd += [
        "-ss",
        f"{max(0.0, float(ts)):.3f}",
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    try:
        timeout = None
        if deadline_mono is not None:
            timeout = max(0.05, deadline_mono - time.perf_counter())
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    arr = np.frombuffer(proc.stdout, dtype=np.uint8)
    if arr.size == 0:
        return None
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame if frame is not None and getattr(frame, "size", 0) > 0 else None


def _use_ffmpeg_hw_fallback() -> bool:
    """Optional ffmpeg CUDA fallback after OpenCV miss."""
    try:
        from app_config.app_config import app_config

        raw = app_config.get("processor.record_hires_ffmpeg_hw")
        if raw is None:
            return False
        return bool(raw)
    except Exception:
        return False


def _record_hires_nvdec_enabled() -> bool:
    """Prefer persistent GStreamer nvv4l2decoder for hires MP4 seeks (Orin)."""
    try:
        from app_config.app_config import app_config

        raw = app_config.get("processor.record_hires_nvdec")
        if raw is not None:
            return bool(raw)
        enc = str(app_config.get("video.encoding") or "").strip().lower()
        return enc in {"jetson", "orin", "nvenc", "nvmpi"}
    except Exception:
        return False


_gst_probe: bool | None = None


def _gst_nvdec_available() -> bool:
    global _gst_probe
    if _gst_probe is not None:
        return _gst_probe
    try:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        Gst.init(None)
        _gst_probe = Gst.ElementFactory.find("nvv4l2decoder") is not None
    except Exception:
        _gst_probe = False
    return _gst_probe


class _GstNvdecSession:
    """Persistent NVDEC pipeline: seek + appsink pull (BGRx → BGR)."""

    def __init__(self, video_path: str):
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst, GLib

        self._Gst = Gst
        self._GLib = GLib
        self.path = os.path.abspath(video_path)
        loc = self.path.replace('"', '\\"')
        desc = (
            f'filesrc location="{loc}" ! qtdemux ! h264parse ! '
            "nvv4l2decoder enable-max-performance=1 ! "
            "nvvidconv ! video/x-raw,format=BGRx ! "
            "appsink name=sink emit-signals=false sync=false max-buffers=2 drop=true"
        )
        self._pipe = Gst.parse_launch(desc)
        self._sink = self._pipe.get_by_name("sink")
        self._bus = self._pipe.get_bus()
        self._ctx = GLib.MainContext.default()
        self._pipe.set_state(Gst.State.PAUSED)
        if not self._pump(8.0):
            raise RuntimeError("gst nvdec preroll failed")
        # Warm first buffer, then PLAYING for fast seeks.
        self._sink.emit("try-pull-preroll", 3 * Gst.SECOND)
        self._pipe.set_state(Gst.State.PLAYING)
        self._pump(2.0)

    def _pump(self, timeout_s: float) -> bool:
        Gst = self._Gst
        end = time.perf_counter() + timeout_s
        while time.perf_counter() < end:
            while self._ctx.pending():
                self._ctx.iteration(False)
            msg = self._bus.timed_pop_filtered(30 * Gst.MSECOND, Gst.MessageType.ANY)
            if msg is None:
                ret, state, _pending = self._pipe.get_state(0)
                if ret != Gst.StateChangeReturn.ASYNC and state in (
                    Gst.State.PAUSED,
                    Gst.State.PLAYING,
                ):
                    return True
                continue
            if msg.type == Gst.MessageType.ERROR:
                return False
            if msg.type in (Gst.MessageType.ASYNC_DONE, Gst.MessageType.EOS):
                return True
        ret, state, _pending = self._pipe.get_state(0)
        return state in (Gst.State.PAUSED, Gst.State.PLAYING)

    @staticmethod
    def _sample_to_bgr(sample) -> np.ndarray | None:
        if sample is None:
            return None
        from gi.repository import Gst

        buf = sample.get_buffer()
        caps = sample.get_caps().get_structure(0)
        w = int(caps.get_value("width"))
        h = int(caps.get_value("height"))
        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return None
        try:
            arr = np.frombuffer(mapinfo.data, dtype=np.uint8)
            if arr.size < w * h * 4:
                return None
            bgrx = np.ascontiguousarray(arr[: w * h * 4].reshape((h, w, 4)))
            return bgrx[:, :, :3].copy()
        finally:
            buf.unmap(mapinfo)

    def read_at(self, ts: float) -> np.ndarray | None:
        Gst = self._Gst
        ns = int(max(0.0, float(ts)) * Gst.SECOND)
        if not self._pipe.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            ns,
        ):
            return None
        self._pump(2.0)
        sample = self._sink.emit("try-pull-sample", 2 * Gst.SECOND)
        if sample is None:
            sample = self._sink.emit("try-pull-preroll", 1 * Gst.SECOND)
        return self._sample_to_bgr(sample)

    def close(self) -> None:
        try:
            self._pipe.set_state(self._Gst.State.NULL)
        except Exception:
            pass


_cap_cache: dict[str, cv2.VideoCapture] = {}
_gst_cache: dict[str, _GstNvdecSession] = {}
_cap_lock = threading.Lock()


def release_record_hires_captures() -> None:
    """Release cached OpenCV / GST NVDEC sessions (call at end of finalize)."""
    with _cap_lock:
        for cap in _cap_cache.values():
            try:
                cap.release()
            except Exception:
                pass
        _cap_cache.clear()
        for sess in _gst_cache.values():
            try:
                sess.close()
            except Exception:
                pass
        _gst_cache.clear()


def _gst_read_frame(video_path: str, ts: float) -> np.ndarray | None:
    """Seek via persistent nvv4l2decoder session (Orin NVDEC)."""
    if not _record_hires_nvdec_enabled() or not _gst_nvdec_available():
        return None
    abspath = os.path.abspath(video_path)
    with _cap_lock:
        sess = _gst_cache.get(abspath)
        if sess is None:
            try:
                sess = _GstNvdecSession(abspath)
            except Exception as exc:
                logger.debug("gst nvdec open failed path=%s: %s", video_path, exc)
                return None
            _gst_cache[abspath] = sess
        try:
            return sess.read_at(ts)
        except Exception as exc:
            logger.debug("gst nvdec seek failed path=%s ts=%.3f: %s", video_path, ts, exc)
            try:
                sess.close()
            except Exception:
                pass
            _gst_cache.pop(abspath, None)
            return None


def _opencv_read_frame(video_path: str, ts: float) -> np.ndarray | None:
    """Seek one frame via cached VideoCapture (CPU decode fallback)."""
    with _cap_lock:
        cap = _cap_cache.get(video_path)
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                _cap_cache.pop(video_path, None)
                return None
            _cap_cache[video_path] = cap
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if fps > 0.01:
            n = max(0, int(float(ts) * fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, n)
        else:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(ts) * 1000.0))
        ok_local, frame = cap.read()
        if not ok_local:
            frame = None
        if frame is None and float(ts) > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, 0.0)
            ok_local, frame = cap.read()
            if not ok_local:
                frame = None
        return frame


def _read_frame_with_retries(
    video_path: str,
    ts: float,
    *,
    max_attempts: int = 1,
    deadline_mono: float | None = None,
) -> np.ndarray | None:
    """Seek one frame: GST NVDEC → OpenCV reuse → ffmpeg fallback."""
    if deadline_mono is not None and time.perf_counter() >= deadline_mono:
        return None

    frame = _gst_read_frame(video_path, ts)
    if frame is not None:
        return frame

    retry_delays = (0.05,)
    attempts = max(1, min(3, int(max_attempts)))
    for attempt in range(attempts):
        if deadline_mono is not None and time.perf_counter() >= deadline_mono:
            return None
        if attempt > 0:
            time.sleep(retry_delays[min(attempt - 1, len(retry_delays) - 1)])
        frame = _opencv_read_frame(video_path, ts)
        if frame is not None:
            return frame

    if deadline_mono is not None and time.perf_counter() >= deadline_mono:
        return None
    frame = _read_frame_ffmpeg(video_path, ts, hwaccel=False, deadline_mono=deadline_mono)
    if frame is not None:
        return frame
    if _use_ffmpeg_hw_fallback():
        return _read_frame_ffmpeg(video_path, ts, hwaccel=True, deadline_mono=deadline_mono)
    return None


def _crop_has_signal(crop: np.ndarray) -> bool:
    if crop is None or crop.size == 0:
        return False
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        return float(gray.std()) >= 8.0
    except Exception:
        return True


def _crop_from_frame(
    frame: np.ndarray,
    bbox: list[float],
    *,
    pad_frac: float,
) -> np.ndarray | None:
    h, w = frame.shape[:2]
    pad = max(0.0, min(0.25, float(pad_frac)))
    bw = float(bbox[2]) - float(bbox[0])
    bh = float(bbox[3]) - float(bbox[1])
    x1n = max(0.0, float(bbox[0]) - bw * pad)
    y1n = max(0.0, float(bbox[1]) - bh * pad)
    x2n = min(1.0, float(bbox[2]) + bw * pad)
    y2n = min(1.0, float(bbox[3]) + bh * pad)
    x1 = max(0, min(w - 1, int(x1n * w)))
    y1 = max(0, min(h - 1, int(y1n * h)))
    x2 = max(x1 + 1, min(w, int(x2n * w)))
    y2 = max(y1 + 1, min(h, int(y2n * h)))
    crop = frame[y1:y2, x1:x2]
    if crop.size > 0 and _crop_has_signal(crop):
        return crop
    return None


def read_record_hires_crop(
    video_path: str,
    detection: Mapping[str, Any],
    *,
    pad_frac: float | None = None,
    runtime_cfg: Mapping[str, Any] | None = None,
    deadline_mono: float | None = None,
) -> np.ndarray | None:
    """Return BGR crop from main MP4 or None."""
    if not video_path:
        return None
    if deadline_mono is not None and time.perf_counter() >= deadline_mono:
        return None
    # Missing file: fail instantly (no OpenCV/GStreamer/ffmpeg burn of finalize budget).
    if not os.path.isfile(video_path):
        return None
    bbox, ts = pick_bbox_and_timestamp(detection, runtime_cfg=runtime_cfg)
    cam = str(detection.get("camera_id") or detection.get("triggered_camera") or "").strip()
    pad = resolve_crop_pad_frac(runtime_cfg=runtime_cfg) if pad_frac is None else max(0.0, min(0.25, float(pad_frac)))
    try:
        frame = _read_frame_with_retries(video_path, ts, max_attempts=1, deadline_mono=deadline_mono)
        if frame is None:
            logger.warning(
                "record_hires: video seek failed path=%s ts=%.3f camera=%s synced=%s",
                video_path,
                ts,
                cam or "?",
                bool(detection.get("playback_timeline_synced")),
            )
            return None
        crop_hw = numpy_hw(frame)
        if crop_hw is None:
            return None
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            logger.info(
                "record_hires: no bbox, skip full-frame fallback path=%s ts=%.3f camera=%s shape=%sx%s",
                video_path,
                ts,
                cam or "?",
                crop_hw[0],
                crop_hw[1],
            )
            return None
        bbox_list = [float(v) for v in bbox]
        playback_bbox = _bbox_stored_in_playback_space(detection, crop_shape_hw=crop_hw)
        crop_bbox = bbox_list if playback_bbox else remap_bbox_for_record_crop(
            bbox_list,
            detection,
            crop_shape_hw=crop_hw,
            runtime_cfg=runtime_cfg,
        )
        if crop_bbox is None:
            # Prefer skip over classifying an unmapped lores bbox on main MP4
            # (wrong crop → false Unknown / wrong species).
            try:
                from processor_runtime_stats import inc_counter

                inc_counter("record_hires_remap_failed_total")
            except Exception:
                pass
            logger.warning(
                "record_hires: remap failed, skip crop path=%s ts=%.3f camera=%s "
                "shape=%sx%s bbox=%s",
                video_path,
                ts,
                cam or "?",
                crop_hw[0],
                crop_hw[1],
                [round(v, 4) for v in bbox_list],
            )
            return None
        for extra_pad in (pad, min(0.25, pad + 0.06), min(0.25, pad + 0.12)):
            crop = _crop_from_frame(frame, crop_bbox, pad_frac=extra_pad)
            if crop is not None:
                if extra_pad != pad:
                    logger.info(
                        "record_hires: playback pad retry ok camera=%s pad=%.3f",
                        cam or "?",
                        extra_pad,
                    )
                return crop
        det_hw, overlay_hw, playback_hw = resolve_record_crop_geometry(
            detection,
            crop_shape_hw=crop_hw,
            runtime_cfg=runtime_cfg,
        )
        logger.warning(
            "record_hires: crop empty/low-signal path=%s ts=%.3f camera=%s "
            "det=%sx%s overlay=%sx%s playback=%sx%s bbox=%s playback_space=%s",
            video_path,
            ts,
            cam or "?",
            det_hw[0],
            det_hw[1],
            overlay_hw[0],
            overlay_hw[1],
            playback_hw[0],
            playback_hw[1],
            [round(v, 4) for v in bbox_list],
            playback_bbox,
        )
        return None
    except Exception as exc:
        logger.warning(
            "record_hires crop failed path=%s ts=%.3f camera=%s: %s",
            video_path,
            ts,
            cam or "?",
            exc,
        )
        return None


def resolve_enrichment_crop(
    detection: Mapping[str, Any],
    *,
    video_path: str | None,
    mode: str,
    lores_crop: Any = None,
    pad_frac: float | None = None,
    runtime_cfg: Mapping[str, Any] | None = None,
    prefer_lores: bool = False,
    deadline_mono: float | None = None,
) -> tuple[Any, str]:
    """(crop ndarray, source tag): record_hires | best_frame_lores | none."""
    mode_norm = mode if mode in _CROP_SOURCES else "auto"
    lores = lores_crop if lores_crop is not None else detection.get("best_frame")

    def _lores_fallback() -> tuple[Any, str]:
        if isinstance(lores, np.ndarray) and lores.size > 0:
            return lores, "best_frame_lores"
        return None, "none"

    # Explicit prefer_lores only (caller opt-in). Do NOT use as silent quality downgrade:
    # detect/track stay on lores; classifier/ReID/welfare target record_hires crop.
    if prefer_lores or (deadline_mono is not None and time.perf_counter() >= deadline_mono):
        return _lores_fallback()

    if mode_norm in {"record_hires", "auto"} and video_path and not prefer_lores:
        hires = read_record_hires_crop(
            video_path,
            detection,
            pad_frac=pad_frac,
            runtime_cfg=runtime_cfg,
            deadline_mono=deadline_mono,
        )
        if hires is not None:
            return hires, "record_hires"

    # Hires miss → in-memory lores crop (architecture fallback, not a budget "optimization").
    return _lores_fallback()


def track_as_detection(
    track: Mapping[str, Any],
    *,
    camera_id: str | None = None,
) -> dict[str, Any]:
    return {
        "start_time": track.get("start_time"),
        "end_time": track.get("end_time"),
        "frames": track.get("frames") or [],
        "key_frames": track.get("key_frames") or [],
        "best_frame": track.get("best_frame"),
        "best_frame_score": track.get("best_frame_score"),
        "camera_id": camera_id or track.get("camera_id"),
        "playback_timeline_synced": track.get("playback_timeline_synced"),
    }
