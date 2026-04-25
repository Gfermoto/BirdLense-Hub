"""Feeder-scale state file helpers for MQTT integrations."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from scale_sample_log import append_feeder_scale_sample

logger = logging.getLogger(__name__)

FEEDER_SCALE_STATE_FILE = "feeder_scale_state.json"


def write_feeder_scale_state(
    data_dir: str,
    weight: float | None = None,
    unit: str | None = None,
    *,
    bird_present: bool | None = None,
    history_max_lines: int = 10000,
) -> None:
    """Persist latest feeder weight and/or bird-present state for UI."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, FEEDER_SCALE_STATE_FILE)
        now = datetime.now(timezone.utc).isoformat()
        prev: dict = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    prev = json.load(f)
            except (OSError, json.JSONDecodeError):
                prev = {}
        rec = dict(prev)
        rec["updated_at"] = now
        if weight is not None:
            u = unit or rec.get("unit") or "kg"
            u = str(u).strip().lower()[:8] or "kg"
            rec["weight"] = float(weight)
            rec["unit"] = u
            append_feeder_scale_sample(data_dir, float(weight), u, max_lines=history_max_lines)
        if bird_present is not None:
            rec["bird_present"] = bool(bird_present)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    except OSError as err:
        logger.debug("write_feeder_scale_state: %s", err)
