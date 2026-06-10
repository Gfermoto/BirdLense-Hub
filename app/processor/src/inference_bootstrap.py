"""OpenVINO / inference bootstrap validation before YOLO load (#618)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InferenceBootstrapPlan:
    requested_backend: str
    effective_backend: str
    openvino_path: str
    auto_torch_fallback: bool
    auto_torch_fallback_reason: str | None = None


def _resolve_openvino_config_path(app_config: Mapping[str, Any], processor_root: str) -> str:
    import os

    from inference.binary_paths import resolve_relative_to_processor_root

    env_ov = (os.environ.get("BIRDLENSE_BINARY_OPENVINO_PATH") or "").strip()
    if env_ov:
        if os.path.isabs(env_ov):
            return env_ov
        return resolve_relative_to_processor_root(env_ov, processor_root)
    rel_ov = app_config.get("processor.models.binary_openvino")
    rel_ov_s = str(rel_ov).strip() if rel_ov is not None else ""
    if not rel_ov_s:
        return ""
    return resolve_relative_to_processor_root(rel_ov_s, processor_root)


def validate_inference_at_bootstrap(app_config: Mapping[str, Any]) -> InferenceBootstrapPlan:
    """
    Fail-fast when ``inference_backend=openvino`` but IR path is missing or invalid.

    For ``auto``, record planned torch fallback when OpenVINO was configured but unusable.
    Does not load YOLO weights.
    """
    from inference.binary_paths import (
        detector_weights_available,
        processor_package_root,
        resolve_binary_detector_weight_path,
    )
    from inference.selector import (
        openvino_binary_enabled,
        openvino_runtime_available,
        resolve_inference_backend,
    )

    processor_root = processor_package_root()
    requested = resolve_inference_backend(app_config)
    ov_allowed = openvino_binary_enabled(app_config)
    ov_path = _resolve_openvino_config_path(app_config, processor_root) if ov_allowed else ""

    if requested == "openvino":
        if not ov_allowed:
            raise RuntimeError(
                "processor.inference_backend=openvino but processor.openvino_binary_enabled=false",
            )
        if not ov_path:
            raise FileNotFoundError(
                "OpenVINO binary detector path missing: set processor.models.binary_openvino "
                "or environment variable BIRDLENSE_BINARY_OPENVINO_PATH "
                "(export: yolo export ... format=openvino).",
            )
        if not detector_weights_available(ov_path):
            raise FileNotFoundError(
                f"OpenVINO IR bundle missing or incomplete: {ov_path}. "
                "Provide a directory with matching *.xml + *.bin or a single .xml with .bin.",
            )
        if not openvino_runtime_available():
            raise RuntimeError(
                "OpenVINO runtime unavailable in this container. "
                "Install openvino or set processor.inference_backend=auto/torch.",
            )
        return InferenceBootstrapPlan(
            requested_backend=requested,
            effective_backend="openvino",
            openvino_path=ov_path,
            auto_torch_fallback=False,
        )

    _path, effective = resolve_binary_detector_weight_path(app_config, processor_root)
    auto_fallback = False
    fallback_reason: str | None = None
    if requested == "auto" and ov_allowed and ov_path:
        if not detector_weights_available(ov_path):
            auto_fallback = effective == "torch"
            fallback_reason = "invalid_openvino_ir"
        elif not openvino_runtime_available():
            auto_fallback = effective == "torch"
            fallback_reason = "openvino_runtime_unavailable"

    return InferenceBootstrapPlan(
        requested_backend=requested,
        effective_backend=effective,
        openvino_path=ov_path,
        auto_torch_fallback=auto_fallback,
        auto_torch_fallback_reason=fallback_reason,
    )


def record_inference_bootstrap_metrics(plan: InferenceBootstrapPlan) -> None:
    from processor_runtime_stats import inc_counter, set_gauge

    set_gauge("inference_backend_requested", plan.requested_backend)
    set_gauge("inference_backend_effective", plan.effective_backend)
    if plan.auto_torch_fallback:
        inc_counter("inference_openvino_auto_torch_fallback_total")
        if plan.auto_torch_fallback_reason:
            set_gauge("inference_auto_torch_fallback_reason", plan.auto_torch_fallback_reason)
        logger.warning(
            "Inference auto backend fallback at bootstrap: requested=%s effective=%s reason=%s openvino_path=%s",
            plan.requested_backend,
            plan.effective_backend,
            plan.auto_torch_fallback_reason,
            plan.openvino_path or "(unset)",
        )


def publish_inference_backend_effective(
    *,
    requested_backend: str,
    effective_backend: str,
    auto_fallback: bool = False,
    fallback_reason: str | None = None,
) -> None:
    """Publish post-stack effective backend to gauges + processor heartbeat fields."""
    from processor_runtime_stats import inc_counter, set_gauge
    from processor_support import processor_status

    req = str(requested_backend or "torch").strip().lower()
    eff = str(effective_backend or "torch").strip().lower()
    set_gauge("inference_backend_requested", req)
    set_gauge("inference_backend_effective", eff)
    processor_status["inference_backend_requested"] = req
    processor_status["inference_backend_effective"] = eff
    if auto_fallback or (req in ("auto", "openvino") and eff == "torch"):
        processor_status["inference_auto_torch_fallback"] = True
        if fallback_reason:
            processor_status["inference_auto_torch_fallback_reason"] = fallback_reason
        if auto_fallback:
            inc_counter("inference_openvino_auto_torch_fallback_total")
