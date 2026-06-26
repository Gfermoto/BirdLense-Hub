"""Резолв пути к весам бинарного детектора.

torch ``.pt`` / ONNX / TensorRT.
"""

from __future__ import annotations

import os
from typing import Any, Mapping


def processor_package_root() -> str:
    """Каталог ``app/processor`` (рядом ``models/``, ``src/``)."""
    inference_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(inference_dir)
    return os.path.dirname(src_dir)


def resolve_relative_to_processor_root(
    rel_or_abs: str,
    processor_root: str,
) -> str:
    """Абсолютный путь: как есть или относительно корня пакета процессора."""
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.join(processor_root, rel_or_abs)


def detector_weights_available(path: str) -> bool:
    """``.pt`` / ``.onnx`` / TensorRT ``.engine`` file exists."""
    if not path:
        return False
    if os.path.isfile(path):
        return path.endswith((".pt", ".onnx", ".engine"))
    return False


def resolve_binary_detector_weight_path(
    app_config: Mapping[str, Any],
    processor_root: str | None = None,
) -> tuple[str, str]:
    """Вернуть ``(абсолютный_путь, inference_backend)``."""
    from inference.selector import resolve_inference_backend

    root = processor_root if processor_root is not None else processor_package_root()
    requested_backend = resolve_inference_backend(app_config)

    if requested_backend == "tensorrt":
        raw_trt = (
            os.environ.get("BIRDLENSE_BINARY_TENSORRT_PATH")
            or app_config.get("processor.models.binary_tensorrt")
            or app_config.get("processor.models.binary_engine")
            or ""
        )
        p = ""
        if raw_trt:
            p = resolve_relative_to_processor_root(str(raw_trt).strip(), root)
        if p and detector_weights_available(p):
            return (p, "tensorrt")
        rel_pt = str(app_config.get("processor.models.binary") or "").strip()
        if rel_pt:
            p_pt = resolve_relative_to_processor_root(rel_pt, root)
            if detector_weights_available(p_pt):
                import logging

                logging.getLogger(__name__).warning(
                    "TensorRT engine missing at %s; falling back to torch .pt at %s",
                    p or raw_trt,
                    p_pt,
                )
                return (p_pt, "torch")
        if p:
            return (p, "tensorrt")

    default_bin = "models/detection/weights/yolo11n.pt"
    rel = app_config.get("processor.models.binary", default_bin)
    p = resolve_relative_to_processor_root(str(rel).strip(), root)
    return (p, "torch")