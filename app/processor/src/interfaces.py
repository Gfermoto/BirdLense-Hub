"""Structural typing for the processor inference pipeline ([#295](https://github.com/Gfermoto/BirdLense-Hub/issues/295)).

``DetectionStrategy`` (ABC) in ``detection_strategy`` satisfies
:class:`DetectionStrategyProtocol` structurally — no inheritance required.
Use the Protocol in annotations and stub implementations in tests without loading YOLO weights.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np


class DetectionStrategyProtocol(Protocol):
    """Minimal surface used by :class:`frame_processor.FrameProcessor` (detect + reset)."""

    def detect(
        self,
        frame: np.ndarray,
        tracker_config: str,
        *,
        min_confidence: float,
    ) -> list[Any]: ...

    def reset(self) -> None: ...
