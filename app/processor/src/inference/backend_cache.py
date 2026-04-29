"""Кэш последнего успешного выбора inference backend (#371)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def inference_backend_cache_path(processor_root: str) -> str:
    """``app/data/processor/inference_backend_cache.json`` относительно корня ``app/processor``."""
    app_root = os.path.abspath(os.path.join(processor_root, ".."))
    base = os.path.join(app_root, "data", "processor")
    return os.path.join(base, "inference_backend_cache.json")


def write_inference_backend_cache(
    processor_root: str,
    *,
    backend: str,
    binary_model_path: str,
    classifier_backend: str | None = None,
    classifier_model_path: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Записать JSON о последнем успешном старте (best-effort, не критично для прод)."""
    path = inference_backend_cache_path(processor_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload: dict[str, Any] = {
        "backend": backend,
        "detector_backend": backend,
        "binary_model_path": binary_model_path,
        "resolved_at_unix": time.time(),
    }
    if classifier_backend:
        payload["classifier_backend"] = classifier_backend
    if classifier_model_path:
        payload["classifier_model_path"] = classifier_model_path
    if extra:
        payload.update(dict(extra))
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.debug("inference backend cache write skipped: %s", e)


def read_inference_backend_cache(processor_root: str) -> dict[str, Any] | None:
    path = inference_backend_cache_path(processor_root)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
