"""Apply processor.openvino.profile / num_requests to Ultralytics YOLO OpenVINO backend (#644)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

_OPENVINO_PROFILE_HINT = {
    "latency": "LATENCY",
    "throughput": "THROUGHPUT",
}


def build_openvino_compile_config(tuning: Mapping[str, Any]) -> dict[str, str]:
    """Map resolve_openvino_tuning() output to OpenVINO compile_model config."""
    profile = str(tuning.get("profile") or "latency").strip().lower()
    hint = _OPENVINO_PROFILE_HINT.get(profile, "LATENCY")
    cfg: dict[str, str] = {"PERFORMANCE_HINT": hint}
    try:
        num_requests = int(tuning.get("num_requests") or 0)
    except (TypeError, ValueError):
        num_requests = 0
    if num_requests > 0:
        cfg["NUM_STREAMS"] = str(num_requests)
    elif profile == "latency":
        cfg["NUM_STREAMS"] = "1"
    return cfg


def resolve_ultralytics_openvino_device_name(device: str | None) -> str:
    """Ultralytics ``intel:gpu`` → OpenVINO device name ``GPU``."""
    d = str(device or "CPU").strip().lower()
    if d in ("intel:gpu", "igpu", "gpu", "gpu.0"):
        return "GPU"
    if d in ("intel:cpu", "cpu"):
        return "CPU"
    if d in ("intel:npu", "npu"):
        return "NPU"
    if d.startswith("intel:"):
        return d.split(":", 1)[1].upper()
    return str(device or "CPU")


def _tuning_fingerprint(tuning: Mapping[str, Any], device: str) -> tuple[str, int, str]:
    try:
        nr = int(tuning.get("num_requests") or 0)
    except (TypeError, ValueError):
        nr = 0
    return (str(tuning.get("profile") or "latency"), nr, str(device or ""))


def _find_autobackend(yolo: Any) -> Any | None:
    for root in (yolo, getattr(yolo, "predictor", None), getattr(yolo, "model", None)):
        if root is None:
            continue
        if getattr(root, "ov_compiled_model", None) is not None and getattr(root, "ov_model", None) is not None:
            return root
        inner = getattr(root, "model", None)
        if inner is not None and getattr(inner, "ov_compiled_model", None) is not None:
            return inner
    return None


def apply_openvino_ultralytics_tuning(
    yolo: Any,
    *,
    device: str | None,
    app_config: Mapping[str, Any] | None = None,
    profile_overrides: Mapping[str, Any] | None = None,
) -> bool:
    """Recompile Ultralytics OpenVINO backend with latency/num_requests from config."""
    from processor_runtime_profile import resolve_openvino_tuning

    autoback = _find_autobackend(yolo)
    if autoback is None:
        try:
            import numpy as np

            yolo.predict(
                np.zeros((32, 32, 3), dtype=np.uint8),
                verbose=False,
                device=device,
            )
            autoback = _find_autobackend(yolo)
        except Exception:
            logger.debug("OpenVINO tuning: YOLO backend warmup failed", exc_info=True)
    if autoback is None:
        return False

    ov_model = getattr(autoback, "ov_model", None)
    if ov_model is None:
        return False

    cfg_obj = app_config if app_config is not None else {}
    tuning = resolve_openvino_tuning(cfg_obj, profile_overrides=profile_overrides)
    compile_cfg = build_openvino_compile_config(tuning)
    ov_dev = resolve_ultralytics_openvino_device_name(
        device or getattr(autoback, "device", None) or getattr(autoback, "device_name", None),
    )

    fp = _tuning_fingerprint(tuning, ov_dev)
    if getattr(autoback, "_birdlense_ov_tuning_fp", None) == fp:
        return True

    import openvino as ov

    core = ov.Core()
    try:
        compiled = core.compile_model(ov_model, ov_dev, compile_cfg)
    except Exception as exc:
        logger.warning("OpenVINO YOLO recompile failed on %s: %s", ov_dev, exc)
        if ov_dev == "CPU":
            return False
        try:
            compiled = core.compile_model(ov_model, "CPU", compile_cfg)
            ov_dev = "CPU"
        except Exception:
            logger.debug("OpenVINO YOLO CPU fallback compile failed", exc_info=True)
            return False

    autoback.ov_compiled_model = compiled
    hint = compile_cfg.get("PERFORMANCE_HINT", "LATENCY")
    if hasattr(autoback, "inference_mode"):
        autoback.inference_mode = hint
    autoback._birdlense_ov_tuning_fp = fp
    logger.info(
        "OpenVINO YOLO tuning applied: profile=%s num_requests=%s device=%s hint=%s",
        tuning.get("profile"),
        tuning.get("num_requests"),
        ov_dev,
        hint,
    )
    return True


def ensure_openvino_track_tuning(
    yolo: Any,
    runtime_cfg: Mapping[str, Any],
    *,
    inference_backend: str,
    device: str | None,
    profile_overrides: Mapping[str, Any] | None = None,
) -> None:
    """Ensure track()/predict() OpenVINO backend matches processor.openvino.* tuning."""
    if (inference_backend or "").strip().lower() != "openvino":
        return
    apply_openvino_ultralytics_tuning(
        yolo,
        device=device,
        app_config=runtime_cfg,
        profile_overrides=profile_overrides,
    )


def classifier_async_safe_on_openvino_igpu(
    app_config: Mapping[str, Any],
    *,
    classifier_backend: str,
    classifier_device: str | None,
) -> bool:
    """
    Async classifier worker is safe when enabled in config.

    OpenVINO on ``intel:gpu`` runs in a background thread — decouples Birder from binary track().
    """
    if not bool(app_config.get("processor.classifier_async_enabled", True)):
        return False
    backend = (classifier_backend or "").strip().lower()
    if backend != "openvino":
        return True
    dev = str(classifier_device or app_config.get("processor.classifier_inference_device") or "auto").strip().lower()
    if dev in ("intel:cpu", "cpu"):
        return True
    return dev in ("", "auto", "intel:gpu", "gpu", "igpu", "gpu.0", "intel:npu", "npu")
