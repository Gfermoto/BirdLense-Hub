"""Runtime DINOv2 Re-ID enrichment for video detections."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import socket
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
    cfg = str(_cfg_get("processor.reid.device", "auto") or "auto").strip()
    if cfg and cfg.lower() != "auto":
        return cfg
    inferred = (os.environ.get("BIRDLENSE_INFERENCE_DEVICE") or "").strip()
    if not inferred:
        inferred = str(_cfg_get("processor.inference_device", "") or "").strip()
    if inferred.lower().startswith("intel:"):
        return inferred
    try:
        import torch
    except ImportError:
        _LOG.debug("reid: torch unavailable, device=cpu")
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_reid_backend(device: str) -> str:
    env = (os.environ.get("BIRDLENSE_REID_BACKEND") or "").strip().lower()
    if env in ("torch", "openvino"):
        return env
    cfg = str(_cfg_get("processor.reid.inference_backend", "auto") or "auto").strip().lower()
    if cfg in ("torch", "openvino"):
        return cfg
    # auto
    if str(device or "").strip().lower().startswith("intel:"):
        return "openvino"
    return "torch"


def _resolve_torch_device_name(device: str) -> str:
    d = str(device or "").strip().lower()
    if not d or d == "auto":
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    if d.startswith("intel:"):
        return "cpu"
    return d


def _resolve_openvino_device_name(device: str) -> str:
    d = str(device or "").strip().lower()
    if d in ("", "auto", "gpu", "intel:gpu"):
        return "GPU"
    if d in ("cpu", "intel:cpu"):
        return "CPU"
    if d in ("npu", "intel:npu"):
        return "NPU"
    return d.upper()


def _hub_cache_dir() -> str:
    env = (os.environ.get("BIRDLENSE_REID_HUB_CACHE_DIR") or "").strip()
    if env:
        return env
    cfg = str(_cfg_get("processor.reid.hub_cache_dir", "") or "").strip()
    return cfg


def _hub_repo_local_path() -> str:
    env = (os.environ.get("BIRDLENSE_REID_HUB_REPO_LOCAL_PATH") or "").strip()
    if env:
        return env
    return str(_cfg_get("processor.reid.hub_repo_local_path", "") or "").strip()


def _hub_download_timeout_seconds() -> float:
    try:
        val = float(_cfg_get("processor.reid.hub_download_timeout_seconds", 15.0))
    except (TypeError, ValueError):
        val = 15.0
    return max(1.0, val)


def _pick_cls_embedding(features: Any) -> Any:
    import torch

    if isinstance(features, torch.Tensor):
        if features.dim() == 3:
            return features[:, 0, :]
        if features.dim() == 2:
            return features
        raise RuntimeError(f"unexpected tensor shape {tuple(features.shape)}")
    if isinstance(features, dict):
        for key in ("x_norm_clstoken", "x_prenorm_clstoken", "cls_token"):
            t = features.get(key)
            if torch.is_tensor(t):
                return t.squeeze(1) if t.dim() == 3 else t
        for value in features.values():
            if torch.is_tensor(value) and value.dim() in (2, 3):
                return value.squeeze(1) if value.dim() == 3 else value
    raise RuntimeError("cannot interpret DINOv2 forward_features output")


def _infer_input_side(model: Any) -> int:
    patch_embed = getattr(model, "patch_embed", None)
    if patch_embed is None:
        return 518
    img_size = getattr(patch_embed, "img_size", None)
    if isinstance(img_size, tuple) and img_size:
        return int(img_size[0])
    if isinstance(img_size, int):
        return int(img_size)
    return 518


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
        model_name = str(_cfg_get("processor.reid.model", "dinov2_vits14") or "dinov2_vits14").strip()
        raw_device = _resolve_reid_device()
        backend = _resolve_reid_backend(raw_device)
        started = time.time()
        try:
            import torch
            import torch.nn.functional as F

            hub_cache = _hub_cache_dir()
            if hub_cache:
                try:
                    torch.hub.set_dir(hub_cache)
                except Exception:
                    _LOG.warning("Cannot set torch.hub dir to %s", hub_cache)
            local_repo = _hub_repo_local_path()
            if local_repo and os.path.isdir(local_repo):
                model = torch.hub.load(  # nosec B614: local_repo is operator-controlled.
                    local_repo,
                    model_name,
                    source="local",
                )
                set_gauge("reid.runtime.hub_source", "local")
            else:
                prev_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(_hub_download_timeout_seconds())
                try:
                    model = torch.hub.load(  # nosec B614: fallback is official upstream DINOv2 entrypoint.
                        "facebookresearch/dinov2",
                        model_name,
                    )
                finally:
                    socket.setdefaulttimeout(prev_timeout)
                set_gauge("reid.runtime.hub_source", "remote")
            model.eval()
            side = _infer_input_side(model)
            if backend == "openvino":
                import openvino as ov

                class _EmbeddingWrapper(torch.nn.Module):
                    def __init__(self, base_model):
                        super().__init__()
                        self.base_model = base_model

                    def forward(self, x):
                        feats = self.base_model.forward_features(x)
                        vec = _pick_cls_embedding(feats)
                        return F.normalize(vec.float(), dim=-1)

                wrapper = _EmbeddingWrapper(model.to(torch.device("cpu")).eval())
                example = torch.zeros((1, 3, side, side), dtype=torch.float32)
                ov_model = ov.convert_model(wrapper, example_input=example)
                core = ov.Core()
                ov_device = _resolve_openvino_device_name(raw_device)
                try:
                    compiled = core.compile_model(ov_model, ov_device)
                    effective_device = ov_device
                except Exception:
                    compiled = core.compile_model(ov_model, "CPU")
                    effective_device = "CPU"
                _MODEL_STATE = {
                    "model_name": model_name,
                    "device": raw_device,
                    "backend": "openvino",
                    "effective_device": effective_device,
                    "compiled_model": compiled,
                    "input_name": compiled.inputs[0].any_name,
                    "side": side,
                }
            else:
                torch_device = _resolve_torch_device_name(raw_device)
                model.to(torch.device(torch_device))
                _MODEL_STATE = {
                    "model_name": model_name,
                    "device": torch_device,
                    "backend": "torch",
                    "effective_device": torch_device,
                    "model": model,
                    "side": side,
                }
            observe_timing("reid_model_load", (time.time() - started) * 1000.0)
            set_gauge("reid.runtime.enabled", True)
            set_gauge("reid.runtime.device", _MODEL_STATE.get("effective_device"))
            set_gauge("reid.runtime.backend", _MODEL_STATE.get("backend"))
            set_gauge("reid.runtime.model", model_name)
            return _MODEL_STATE
        except Exception as exc:
            _MODEL_FAILED = True
            set_gauge("reid.runtime.enabled", False)
            _LOG.warning("Runtime DINOv2 disabled: failed to load model (%s)", exc)
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
        _LOG.debug("reid: cv2/torch import failed for embedding", exc_info=True)
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
    backend = str(state.get("backend") or "torch").strip().lower()
    if backend == "openvino":
        try:
            out_data = state["compiled_model"]({state["input_name"]: x4})
            if hasattr(out_data, "values"):
                out = np.asarray(next(iter(out_data.values())), dtype=np.float32)
            elif isinstance(out_data, (list, tuple)):
                out = np.asarray(out_data[0], dtype=np.float32)
            else:
                out = np.asarray(out_data, dtype=np.float32)
            out = np.squeeze(out).astype(np.float32)
        except Exception:
            _LOG.debug("reid: openvino embedding inference failed", exc_info=True)
            return None
    else:
        try:
            import torch
            import torch.nn.functional as F
        except Exception:
            _LOG.debug("reid: torch import failed for embedding", exc_info=True)
            return None
        t = torch.from_numpy(x4).to(torch.device(state["device"]))
        with torch.inference_mode():
            feats = state["model"].forward_features(t)
            vec = _pick_cls_embedding(feats)
            vec = F.normalize(vec.float(), dim=-1).squeeze(0)
        out = vec.detach().cpu().numpy().astype(np.float32)
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
    for det in detections:
        if processed >= max(0, int(max_detections)):
            break
        if str(det.get("source") or "").strip().lower() != "video":
            continue
        if float(det.get("best_frame_score") or 0.0) < float(min_best_frame_score):
            continue
        crop = det.get("best_frame")
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
    state = _ensure_model_state()
    if state is None:
        return detections

    started = time.time()
    out = apply_runtime_reid_metadata(
        detections,
        embed_crop=lambda crop: _to_embedding(crop, state=state),
        load_candidates=_load_species_candidates,
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
