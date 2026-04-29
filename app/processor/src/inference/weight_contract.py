"""Проверка имён классов бинарного детектора при загрузке весов (#368)."""

from __future__ import annotations

import logging
from typing import AbstractSet, Any

from detector_labels import normalize_detector_label

_CONTRACT_MODES = frozenset({"off", "warn", "enforce"})


def coerce_detector_names(names: Any) -> dict[int, str]:
    """Ultralytics: ``model.names`` обычно dict; нормализуем к ``dict[int,str]``."""
    if names is None:
        return {}
    if isinstance(names, dict):
        out: dict[int, str] = {}
        for k, v in names.items():
            try:
                ik = int(k)
            except (TypeError, ValueError):
                continue
            out[ik] = str(v)
        return out
    if isinstance(names, (list, tuple)):
        return {i: str(x) for i, x in enumerate(names)}
    return {}


def validate_detector_weight_contract(
    names: Any,
    detector_scope: AbstractSet[str],
    mode: str,
    logger: logging.Logger,
) -> None:
    """
    Проверить, что после нормализации покрыты все метки из ``detector_scope``.

    - ``Background`` не должен входить в ``detector_scope`` (hard-negative).
    - Режим ``off``: без проверок.
    - ``warn`` / ``enforce``: при нехватке классов под scope — warning или raise.

    Legacy двухклассовые веса могут не содержать Rodent — при ``enforce`` упадёт;
    до миграции весов используйте ``warn`` (дефолт).
    """
    m = (mode or "warn").strip().lower()
    if m not in _CONTRACT_MODES:
        m = "warn"
    if m == "off":
        return

    nd = coerce_detector_names(names)
    normalized_set = {normalize_detector_label(v) for v in nd.values()}
    missing = sorted(detector_scope - normalized_set)

    messages: list[str] = []
    if detector_scope & {"Background"}:
        messages.append(
            "processor.detector_scope must not include Background (hard-negative; see docs/CV_ML_PREP.md).",
        )
    if missing:
        scope_s = sorted(detector_scope)
        norm_s = sorted(normalized_set)
        messages.append(
            "Detector names after normalization miss scoped labels "
            f"{missing} (detector_scope={scope_s}; model has {norm_s}).",
        )

    if not messages:
        return
    text = " ".join(messages) + (" (see docs/TROUBLESHOOTING.md#detector-weight-contract-mismatch).")
    if m == "enforce":
        raise ValueError(f"Detector weight contract: {text}")
    logger.warning("Detector weight contract: %s", text)
