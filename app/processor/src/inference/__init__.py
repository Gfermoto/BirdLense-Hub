"""Абстракция инференса процессора. ONNX Runtime / torch для бинарного детектора + контракт весов."""

import sys

if sys.version_info >= (3, 7):
    from .selector import (
        assert_backend_supported,
        resolve_classifier_inference_backend,
        resolve_classifier_inference_device,
        resolve_inference_backend,
        resolve_inference_device,
    )

    __all__ = [
        "assert_backend_supported",
        "resolve_inference_backend",
        "resolve_classifier_inference_backend",
        "resolve_classifier_inference_device",
        "resolve_inference_device",
    ]
else:
    # Jetson TRT worker (python3.6): selector uses py3.7+ syntax.
    __all__ = []