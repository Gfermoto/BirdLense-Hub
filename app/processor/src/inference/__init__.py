"""Абстракция инференса процессора (roadmap #371). Torch/OpenVINO binary detector + контракт весов."""

from __future__ import annotations

from .selector import (
    assert_backend_supported,
    openvino_binary_enabled,
    openvino_runtime_available,
    resolve_classifier_inference_backend,
    resolve_classifier_inference_device,
    resolve_inference_backend,
    resolve_inference_device,
    resolve_openvino_device_policy,
    resolve_openvino_num_requests,
    resolve_openvino_profile,
)

__all__ = [
    "assert_backend_supported",
    "openvino_binary_enabled",
    "openvino_runtime_available",
    "resolve_inference_backend",
    "resolve_classifier_inference_backend",
    "resolve_classifier_inference_device",
    "resolve_inference_device",
    "resolve_openvino_device_policy",
    "resolve_openvino_num_requests",
    "resolve_openvino_profile",
]
