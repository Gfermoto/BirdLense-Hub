"""Inference bootstrap validation before YOLO load."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InferenceBootstrapPlan:
    requested_backend: str
    effective_backend: str
    auto_torch_fallback: bool
    auto_torch_fallback_reason: str | None = None


def validate_inference_at_bootstrap(app_config: Mapping[str, Any]) -> InferenceBootstrapPlan:
    """Resolve effective inference backend at bootstrap. Does not load YOLO weights."""
    from inference.binary_paths import (
        processor_package_root,
        resolve_binary_detector_weight_path,
    )
    from inference.selector import resolve_inference_backend

    processor_root = processor_package_root()
    requested = resolve_inference_backend(app_config)
    _path, effective = resolve_binary_detector_weight_path(app_config, processor_root)

    return InferenceBootstrapPlan(
        requested_backend=requested,
        effective_backend=effective,
        auto_torch_fallback=False,
        auto_torch_fallback_reason=None,
    )


def record_inference_bootstrap_metrics(plan: InferenceBootstrapPlan) -> None:
    from processor_runtime_stats import set_gauge

    set_gauge("inference_backend_requested", plan.requested_backend)
    set_gauge("inference_backend_effective", plan.effective_backend)


def publish_inference_backend_effective(
    *,
    requested_backend: str,
    effective_backend: str,
    auto_fallback: bool = False,
    fallback_reason: str | None = None,
) -> None:
    """Publish post-stack effective backend to gauges + processor heartbeat fields."""
    from processor_runtime_stats import set_gauge
    from processor_support import processor_status

    req = str(requested_backend or "torch").strip().lower()
    eff = str(effective_backend or "torch").strip().lower()
    set_gauge("inference_backend_requested", req)
    set_gauge("inference_backend_effective", eff)
    processor_status["inference_backend_requested"] = req
    processor_status["inference_backend_effective"] = eff
    if auto_fallback:
        processor_status["inference_auto_torch_fallback"] = True
        if fallback_reason:
            processor_status["inference_auto_torch_fallback_reason"] = fallback_reason
