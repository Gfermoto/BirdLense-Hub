"""Абстракция инференса процессора (roadmap #371). Torch/OpenVINO binary detector + контракт весов."""

from __future__ import annotations

from .selector import assert_backend_supported, resolve_inference_backend

__all__ = ["assert_backend_supported", "resolve_inference_backend"]
