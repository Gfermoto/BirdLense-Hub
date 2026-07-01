"""Runtime Re-ID enrichment for video detections (Ornimetrics ONNX on Orin)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
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
_CANDIDATE_CACHE_LOCK = threading.Lock()
_CANDIDATE_CACHE: dict[str, tuple[float, list[tuple[np.ndarray, str]]]] = {}


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


def _reid_runtime_enabled() -> bool:
    env = (os.environ.get("BIRDLENSE_REID_RUNTIME_ENABLED") or "").strip().lower()
    if env:
        return env in ("1", "true", "yes", "on")
    return _cfg_bool("processor.reid.runtime_enabled", True)


def _resolve_reid_device() -> str:
    env = (os.environ.get("BIRDLENSE_REID_DEVICE") or "").strip()
    if env:
        return env
    cfg = str(_cfg_get("processor.reid.device", "cuda:0") or "cuda:0").strip()
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

        raw_device = _resolve_reid_device()
        started = time.time()
        try:
            from inference.binary_paths import processor_package_root, resolve_relative_to_processor_root

            raw_path = str(_cfg_get("processor.models.reid_embedder", "") or "").strip()
            model_path = (
                resolve_relative_to_processor_root(raw_path, processor_package_root()) if raw_path else ""
            )
            if not model_path or not os.path.isfile(model_path):
                raise FileNotFoundError("Ornimetrics ReID ONNX not found: %s" % model_path)

            import onnxruntime as ort

            session = ort.InferenceSession(model_path, providers=_ort_providers(raw_device))
            inp = session.get_inputs()[0]
            side = int(inp.shape[-1]) if inp.shape[-1] else 224
            _MODEL_STATE = {
                "model_name": "ornimetrics_reid",
                "device": raw_device,
                "backend": "onnxruntime",
                "ort_session": session,
                "input_name": inp.name,
                "side": side,
            }
            observe_timing("reid_model_load", (time.time() - started) * 1000.0)
            set_gauge("reid.runtime.enabled", True)
            set_gauge("reid.runtime.device", raw_device)
            set_gauge("reid.runtime.backend", "onnxruntime")
            set_gauge("reid.runtime.model", "ornimetrics_reid")
            return _MODEL_STATE
        except Exception as exc:
            _MODEL_FAILED = True
            set_gauge("reid.runtime.enabled", False)
            _LOG.warning("Runtime ReID disabled: failed to load model (%s)", exc)
            return None


def prewarm_runtime_reid_model() -> bool:
    """Best-effort startup preload to avoid first-detection latency spikes."""
    if not _reid_runtime_enabled():
        return False
    preload = _cfg_bool("processor.reid.preload_on_start", True)
    if not preload:
        return False
    started = time.time()
    state = _ensure_model_state()
    ok = state is not None
    observe_timing("reid_prewarm", (time.time() - started) * 1000.0)
    if ok:
        inc_counter("reid_runtime_prewarm_ok_total", 1)
    else:
        inc_counter("reid_runtime_prewarm_fail_total", 1)
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
        _LOG.debug("reid: cv2 import failed for embedding", exc_info=True)
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
        ort_session = state["ort_session"]
        inp_name = state["input_name"]
        out = ort_session.run(None, {inp_name: x4})[0]
        out = np.squeeze(out).astype(np.float32)
    except Exception:
        _LOG.debug("reid: onnxruntime embedding inference failed", exc_info=True)
        return None
    if out.ndim != 1 or out.shape[0] <= 0:
        return None
    return out


def _nickname_species_token(species_name: str) -> str:
    raw = str(species_name or "").strip().lower()
    token = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return token[:20] if token else "bird"


def _embedding_fingerprint(embedding: np.ndarray) -> str:
    q = np.round(np.asarray(embedding, dtype=np.float32), 3).astype(np.float32)
    return hashlib.blake2s(q.tobytes(), digest_size=4).hexdigest()


def _generate_auto_nickname(
    *,
    species_name: str,
    embedding: np.ndarray,
    existing_names: set[str],
) -> str:
    base = f"{_nickname_species_token(species_name)}_{_embedding_fingerprint(embedding)}"
    if base not in existing_names:
        existing_names.add(base)
        return base
    idx = 2
    while True:
        cand = f"{base}_{idx}"
        if cand not in existing_names:
            existing_names.add(cand)
            return cand
        idx += 1


def _db_path() -> str:
    data_dir = (os.environ.get("DATA_DIR") or "data").strip() or "data"
    return os.path.join(data_dir, "db", "birdlense.db")


def _load_species_candidates(species_name: str) -> list[tuple[np.ndarray, str]]:
    db_path = _db_path()
    if not os.path.exists(db_path):
        return []

    sql = (
        "SELECT re.embedding_json, vs.individual_nickname "
        "FROM reid_embedding re "
        "JOIN video_species vs ON vs.id = re.video_species_id "
        "JOIN species s ON s.id = vs.species_id "
        "WHERE s.name = ? "
        "AND vs.individual_nickname IS NOT NULL "
        "AND LENGTH(TRIM(vs.individual_nickname)) > 0 "
        "ORDER BY re.id DESC LIMIT 800"
    )
    out: list[tuple[np.ndarray, str]] = []
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        rows = conn.execute(sql, (species_name,)).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()
    for emb_json, nickname in rows:
        try:
            raw = json.loads(emb_json or "[]")
        except ValueError:
            continue
        if not isinstance(raw, list) or not raw:
            continue
        try:
            vec = np.asarray([float(v) for v in raw], dtype=np.float32)
        except (TypeError, ValueError):
            continue
        norm = float(np.linalg.norm(vec))
        if norm <= 1e-9:
            continue
        vec = vec / norm
        out.append((vec, str(nickname).strip()))
    return out


def _load_species_candidates_cached(species_name: str) -> list[tuple[np.ndarray, str]]:
    key = str(species_name or "").strip()
    if not key:
        return []
    try:
        ttl_s = float(_cfg_get("processor.reid.candidate_cache_ttl_seconds", 120.0))
    except (TypeError, ValueError):
        ttl_s = 120.0
    ttl_s = max(1.0, ttl_s)
    now = time.time()
    with _CANDIDATE_CACHE_LOCK:
        hit = _CANDIDATE_CACHE.get(key)
        if hit and now - float(hit[0]) <= ttl_s:
            inc_counter("reid_runtime_candidate_cache_hit_total", 1)
            return list(hit[1])
    rows = _load_species_candidates(key)
    with _CANDIDATE_CACHE_LOCK:
        _CANDIDATE_CACHE[key] = (now, list(rows))
    inc_counter("reid_runtime_candidate_cache_miss_total", 1)
    return rows


def _best_match_nickname(
    embedding: np.ndarray,
    candidates: list[tuple[np.ndarray, str]],
) -> tuple[str | None, float]:
    if not candidates:
        return None, 0.0
    emb_norm = float(np.linalg.norm(embedding))
    if emb_norm <= 1e-9:
        return None, 0.0
    emb = embedding / emb_norm
    best_name = None
    best_score = -1.0
    for cand_vec, cand_name in candidates:
        score = float(np.dot(emb, cand_vec))
        if score > best_score:
            best_score = score
            best_name = cand_name
    if best_name is None:
        return None, 0.0
    return best_name, max(-1.0, min(1.0, best_score))


def apply_runtime_reid_metadata(
    detections: list[dict],
    *,
    embed_crop: Callable[[Any], np.ndarray | None],
    load_candidates: Callable[[str], list[tuple[np.ndarray, str]]],
    model_name: str,
    similarity_threshold: float,
    max_detections: int,
    min_best_frame_score: float,
    flag_low_similarity_for_review: bool,
    video_path: str,
) -> list[dict]:
    if not detections:
        return detections

    processed = 0
    auto_named = 0
    candidate_cache: dict[str, list[tuple[np.ndarray, str]]] = {}
    known_names_cache: dict[str, set[str]] = {}
    auto_generate_nickname = _cfg_bool("processor.reid.auto_generate_nickname_enabled", True)
    include_embedding_payload = _cfg_bool(
        "processor.reid.include_embedding_payload",
        True,
    )
    try:
        max_runtime_ms = float(_cfg_get("processor.reid.max_runtime_ms", 250.0))
    except (TypeError, ValueError):
        max_runtime_ms = 250.0
    max_runtime_ms = max(1.0, max_runtime_ms)
    started = time.perf_counter()
    timed_out = False
    for det in detections:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= max_runtime_ms:
            timed_out = True
            inc_counter("reid_runtime_timeout_total", 1)
            break
        if processed >= max(0, int(max_detections)):
            break
        if str(det.get("source") or "").strip().lower() != "video":
            continue
        if float(det.get("best_frame_score") or 0.0) < float(min_best_frame_score):
            continue
        crop = det.get("best_frame")
        crop_source = "best_frame_lores"
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
                config_key="processor.reid_crop_source",
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
                    det["reid_crop_source"] = crop_source
        except ImportError:
            pass
        if crop is None:
            continue
        embedding = embed_crop(crop)
        if embedding is None:
            continue
        processed += 1
        emb = np.asarray(embedding, dtype=np.float32)
        if emb.ndim != 1 or emb.shape[0] <= 0:
            continue
        norm = float(np.linalg.norm(emb))
        if norm <= 1e-9:
            continue
        emb = emb / norm

        species_name = str(det.get("species_name") or "").strip()
        if species_name not in candidate_cache:
            candidate_cache[species_name] = load_candidates(species_name) if species_name else []
            known_names_cache[species_name] = {
                str(name).strip() for _, name in candidate_cache[species_name] if str(name).strip()
            }
        match_name, score = _best_match_nickname(emb, candidate_cache[species_name])

        track_id = det.get("track_id")
        st = float(det.get("start_time") or 0.0)
        et = float(det.get("end_time") or 0.0)
        crop_key = f"runtime://{video_path}#track={track_id if track_id is not None else 'na'}:{st:.3f}-{et:.3f}"
        det["reid_model"] = model_name
        det["reid_dim"] = int(emb.shape[0])
        if include_embedding_payload:
            det["reid_embedding"] = [round(float(v), 6) for v in emb.tolist()]
        det["reid_crop_key"] = crop_key
        det["reid_similarity"] = round(float(score), 4)

        has_existing_candidates = bool(candidate_cache[species_name])
        is_low_similarity = has_existing_candidates and float(score) < float(similarity_threshold)
        if (
            match_name
            and float(score) >= float(similarity_threshold)
            and not str(det.get("individual_nickname") or "").strip()
        ):
            det["individual_nickname"] = match_name
            auto_named += 1
        if flag_low_similarity_for_review and is_low_similarity:
            det["classifier_needs_review"] = True
            if not str(det.get("review_reason") or "").strip():
                det["review_reason"] = "reid_no_match"
        if auto_generate_nickname and not str(det.get("individual_nickname") or "").strip():
            generated = _generate_auto_nickname(
                species_name=species_name,
                embedding=emb,
                existing_names=known_names_cache.get(species_name, set()),
            )
            det["individual_nickname"] = generated
            auto_named += 1

    inc_counter("reid_runtime_embeddings_total", processed)
    inc_counter("reid_runtime_auto_nickname_total", auto_named)
    if timed_out:
        set_gauge("reid.runtime.last_timeout", True)
    else:
        set_gauge("reid.runtime.last_timeout", False)
    set_gauge("reid.runtime.last_processed_count", processed)
    set_gauge("reid.runtime.last_auto_named_count", auto_named)
    return detections


def enrich_runtime_reid_detections(
    detections: list[dict],
    *,
    video_path: str,
) -> list[dict]:
    if not _reid_runtime_enabled():
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

    started = time.time()
    out = apply_runtime_reid_metadata(
        detections,
        embed_crop=lambda crop: _to_embedding(crop, state=state),
        load_candidates=_load_species_candidates_cached,
        model_name=str(state["model_name"]),
        similarity_threshold=_cfg_float("processor.reid.nickname_similarity_threshold", 0.9),
        max_detections=_cfg_int("processor.reid.max_detections_per_recording", 6),
        min_best_frame_score=_cfg_float("processor.reid.min_best_frame_score", 0.0),
        flag_low_similarity_for_review=_cfg_bool(
            "processor.reid.flag_low_similarity_for_review",
            True,
        ),
        video_path=video_path,
    )
    observe_timing("reid_runtime_enrich", (time.time() - started) * 1000.0)
    return out
