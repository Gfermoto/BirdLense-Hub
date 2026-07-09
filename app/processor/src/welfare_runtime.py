"""Runtime welfare screening for video detections (Ornimetrics ONNX + NPZ on Orin)."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

import numpy as np

from app_config.app_config import app_config
from processor_runtime_stats import inc_counter, observe_timing, set_gauge

_LOG = logging.getLogger(__name__)
_MODEL_LOCK = threading.Lock()
_MODEL_STATE: dict[str, Any] | None = None
_MODEL_FAILED = False


def _cfg_get(key: str, default: Any) -> Any:
    try:
        return app_config.get(key, default)
    except Exception:
        return default


def _cfg_bool(key: str, default: bool) -> bool:
    val = _cfg_get(key, default)
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _cfg_int(key: str, default: int) -> int:
    try:
        return int(_cfg_get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _cfg_float(key: str, default: float) -> float:
    try:
        return float(_cfg_get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _welfare_runtime_enabled() -> bool:
    env = (os.environ.get("BIRDLENSE_WELFARE_RUNTIME_ENABLED") or "").strip().lower()
    if env:
        return env in ("1", "true", "yes", "on")
    return _cfg_bool("processor.welfare.runtime_enabled", True)


def _resolve_welfare_device() -> str:
    env = (os.environ.get("BIRDLENSE_WELFARE_DEVICE") or "").strip()
    if env:
        return env
    cfg = str(_cfg_get("processor.welfare.device", "cuda:0") or "cuda:0").strip()
    if cfg and cfg.lower() != "auto":
        return cfg
    inferred = (os.environ.get("BIRDLENSE_INFERENCE_DEVICE") or "").strip()
    if not inferred:
        inferred = str(_cfg_get("processor.inference_device", "cuda:0") or "cuda:0").strip()
    return inferred or "cuda:0"


def _ort_providers(device: str) -> list[str]:
    d = str(device or "").strip().lower()
    if d.startswith("cuda") or d.startswith("gpu"):
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def _mahalanobis_distance(embedding: np.ndarray, mean: np.ndarray, inv_cov: np.ndarray) -> float:
    emb = np.asarray(embedding, dtype=np.float64).reshape(-1)
    mu = np.asarray(mean, dtype=np.float64).reshape(-1)
    ic = np.asarray(inv_cov, dtype=np.float64)
    if emb.shape[0] != mu.shape[0]:
        raise ValueError("welfare embedding dim mismatch: %s vs %s" % (emb.shape[0], mu.shape[0]))
    delta = emb - mu
    return float(delta @ ic @ delta)


def _ensure_model_state() -> dict[str, Any] | None:
    global _MODEL_STATE
    global _MODEL_FAILED

    if _MODEL_STATE is not None:
        return _MODEL_STATE
    if _MODEL_FAILED:
        return None

    with _MODEL_LOCK:
        if _MODEL_STATE is not None:
            return _MODEL_STATE
        if _MODEL_FAILED:
            return None

        raw_device = _resolve_welfare_device()
        started = time.time()
        try:
            from inference.binary_paths import processor_package_root, resolve_relative_to_processor_root

            embedder_raw = str(_cfg_get("processor.models.welfare_embedder", "") or "").strip()
            scorer_raw = str(_cfg_get("processor.models.welfare_scorer", "") or "").strip()
            embedder_path = (
                resolve_relative_to_processor_root(embedder_raw, processor_package_root())
                if embedder_raw
                else ""
            )
            scorer_path = (
                resolve_relative_to_processor_root(scorer_raw, processor_package_root()) if scorer_raw else ""
            )
            if not embedder_path or not os.path.isfile(embedder_path):
                raise FileNotFoundError("Ornimetrics welfare embedder ONNX not found: %s" % embedder_path)
            if not scorer_path or not os.path.isfile(scorer_path):
                raise FileNotFoundError("Ornimetrics welfare scorer NPZ not found: %s" % scorer_path)

            import onnxruntime as ort

            session = ort.InferenceSession(embedder_path, providers=_ort_providers(raw_device))
            inp = session.get_inputs()[0]
            side = int(inp.shape[-1]) if inp.shape[-1] else 224
            scorer = np.load(scorer_path)
            mean = np.asarray(scorer["mean"], dtype=np.float32)
            inv_cov = np.asarray(scorer["inv_cov"], dtype=np.float32)
            if inv_cov.ndim != 2:
                raise ValueError("welfare_scorer inv_cov must be 2-D")
            embed_dim = int(mean.shape[0]) if mean.ndim == 1 else int(mean.size)
            _MODEL_STATE = {
                "model_name": "ornimetrics_welfare",
                "device": raw_device,
                "backend": "onnxruntime",
                "ort_session": session,
                "input_name": inp.name,
                "side": side,
                "mean": mean,
                "inv_cov": inv_cov,
                "embed_dim": embed_dim,
            }
            observe_timing("welfare_model_load", (time.time() - started) * 1000.0)
            set_gauge("welfare.runtime.enabled", True)
            set_gauge("welfare.runtime.device", raw_device)
            set_gauge("welfare.runtime.backend", "onnxruntime")
            set_gauge("welfare.runtime.model", "ornimetrics_welfare")
            set_gauge("welfare.runtime.embed_dim", embed_dim)
            return _MODEL_STATE
        except Exception as exc:
            _MODEL_FAILED = True
            set_gauge("welfare.runtime.enabled", False)
            _LOG.warning("Runtime welfare disabled: failed to load model (%s)", exc)
            return None


def prewarm_runtime_welfare_model() -> bool:
    """Best-effort startup preload to avoid first-detection latency spikes."""
    if not _welfare_runtime_enabled():
        return False
    preload = _cfg_bool("processor.welfare.preload_on_start", True)
    if not preload:
        return False
    started = time.time()
    state = _ensure_model_state()
    ok = state is not None
    observe_timing("welfare_prewarm", (time.time() - started) * 1000.0)
    if ok:
        inc_counter("welfare_runtime_prewarm_ok_total", 1)
    else:
        inc_counter("welfare_runtime_prewarm_fail_total", 1)
    return ok


def _to_embedding(crop: Any, *, state: dict[str, Any]) -> np.ndarray | None:
    if crop is None:
        return None
    arr = np.asarray(crop)
    if arr.ndim != 3 or arr.shape[2] != 3:
        return None
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)

    try:
        import cv2
    except Exception:
        _LOG.debug("welfare: cv2 import failed for embedding", exc_info=True)
        return None

    rgb = arr[:, :, ::-1]
    side = int(state["side"])
    resized = cv2.resize(rgb, (side, side), interpolation=cv2.INTER_CUBIC)
    x = resized.astype(np.float32) / 255.0
    mean = np.array((0.485, 0.456, 0.406), dtype=np.float32)
    std = np.array((0.229, 0.224, 0.225), dtype=np.float32)
    x = (x - mean) / std
    x = np.transpose(x, (2, 0, 1))
    x4 = np.expand_dims(x, axis=0).astype(np.float32)
    try:
        from onnx_runtime_guard import ort_run

        ort_session = state["ort_session"]
        inp_name = state["input_name"]
        out = ort_run(ort_session, None, {inp_name: x4})[0]
        out = np.squeeze(out).astype(np.float32)
    except Exception:
        _LOG.debug("welfare: onnxruntime embedding inference failed", exc_info=True)
        return None
    if out.ndim != 1 or out.shape[0] <= 0:
        return None
    return out


def apply_runtime_welfare_metadata(
    detections: list[dict],
    *,
    embed_crop: Callable[[Any], np.ndarray | None],
    score_embedding: Callable[[np.ndarray], float],
    model_name: str,
    embed_dim: int,
    distance_review_threshold: float,
    max_detections: int,
    min_best_frame_score: float,
    flag_for_review: bool,
    video_path: str,
) -> list[dict]:
    if not detections:
        return detections

    processed = 0
    flagged = 0
    try:
        max_runtime_ms = float(_cfg_get("processor.welfare.max_runtime_ms", 250.0))
    except (TypeError, ValueError):
        max_runtime_ms = 250.0
    max_runtime_ms = max(1.0, max_runtime_ms)
    started = time.perf_counter()
    timed_out = False
    for det in detections:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= max_runtime_ms:
            timed_out = True
            inc_counter("welfare_runtime_timeout_total", 1)
            break
        if processed >= max(0, int(max_detections)):
            break
        if str(det.get("source") or "").strip().lower() != "video":
            continue
        if float(det.get("best_frame_score") or 0.0) < float(min_best_frame_score):
            continue
        crop = det.get("best_frame")
        try:
            from record_hires_crop import resolve_enrichment_crop, resolve_enrichment_crop_source

            runtime_cfg = None
            try:
                from app_config.app_config import app_config as _cfg

                runtime_cfg = getattr(_cfg, "config", None) or _cfg
            except ImportError:
                pass
            mode = resolve_enrichment_crop_source(
                runtime_cfg,
                config_key="processor.welfare_crop_source",
                default="auto",
            )
            if video_path:
                resolved, crop_source = resolve_enrichment_crop(
                    det,
                    video_path=video_path,
                    mode=mode,
                    lores_crop=crop,
                    runtime_cfg=runtime_cfg,
                )
                if resolved is not None:
                    crop = resolved
                    det["welfare_crop_source"] = crop_source
        except ImportError:
            pass
        if crop is None:
            continue
        embedding = embed_crop(crop)
        if embedding is None:
            continue
        emb = np.asarray(embedding, dtype=np.float32)
        if emb.ndim != 1 or emb.shape[0] <= 0:
            continue
        try:
            distance = float(score_embedding(emb))
        except Exception:
            _LOG.debug("welfare: Mahalanobis scoring failed", exc_info=True)
            continue
        processed += 1
        needs_review = distance >= float(distance_review_threshold)
        det["welfare_model"] = model_name
        det["welfare_embed_dim"] = int(embed_dim)
        det["welfare_distance"] = round(distance, 4)
        det["welfare_needs_review"] = bool(needs_review)
        if needs_review:
            flagged += 1
            if flag_for_review:
                det["classifier_needs_review"] = True
                if not str(det.get("review_reason") or "").strip():
                    det["review_reason"] = "welfare_anomaly"

    inc_counter("welfare_runtime_embeddings_total", processed)
    inc_counter("welfare_runtime_review_flagged_total", flagged)
    if timed_out:
        set_gauge("welfare.runtime.last_timeout", True)
    else:
        set_gauge("welfare.runtime.last_timeout", False)
    set_gauge("welfare.runtime.last_processed_count", processed)
    set_gauge("welfare.runtime.last_flagged_count", flagged)
    return detections


def enrich_runtime_welfare_detections(
    detections: list[dict],
    *,
    video_path: str,
) -> list[dict]:
    if not _welfare_runtime_enabled():
        return detections
    try:
        from bbox_slo import bbox_layers_allowed

        if not bbox_layers_allowed(app_config):
            return detections
    except ImportError:
        pass
    state = _ensure_model_state()
    if state is None:
        return detections

    mean = state["mean"]
    inv_cov = state["inv_cov"]
    started = time.time()
    out = apply_runtime_welfare_metadata(
        detections,
        embed_crop=lambda crop: _to_embedding(crop, state=state),
        score_embedding=lambda emb: _mahalanobis_distance(emb, mean, inv_cov),
        model_name=str(state["model_name"]),
        embed_dim=int(state["embed_dim"]),
        distance_review_threshold=_cfg_float("processor.welfare.distance_review_threshold", 75.0),
        max_detections=_cfg_int("processor.welfare.max_detections_per_recording", 6),
        min_best_frame_score=_cfg_float("processor.welfare.min_best_frame_score", 0.0),
        flag_for_review=_cfg_bool("processor.welfare.flag_for_review", True),
        video_path=video_path,
    )
    observe_timing("welfare_runtime_enrich", (time.time() - started) * 1000.0)
    return out
