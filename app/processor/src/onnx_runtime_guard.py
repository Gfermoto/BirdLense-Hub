"""Serialize ONNX Runtime session.run across concurrent finalize paths."""

from __future__ import annotations

import threading
from typing import Any

_INFERENCE_LOCK = threading.Lock()


def ort_run(session: Any, output_names: Any, input_feed: dict[str, Any]) -> list[Any]:
    with _INFERENCE_LOCK:
        return session.run(output_names, input_feed)
