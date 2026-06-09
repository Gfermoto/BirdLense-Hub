"""Processor heartbeat motion-age monitoring."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.abspath(os.path.join(current_dir, "../.."))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
web_path = os.path.abspath(os.path.join(current_dir, "../../web"))
for path in (app_path, src_path, web_path):
    if path not in sys.path:
        sys.path.insert(0, path)

import processor_support as ps  # noqa: E402


def test_mark_motion_triggered_sets_age_and_heartbeat_field():
    ps.processor_status["last_motion_at"] = None
    with patch("processor_runtime_stats.set_gauge") as set_gauge:
        ps.mark_motion_triggered()
        payload = ps._heartbeat_payload()
    assert ps.processor_status["last_motion_at"]
    set_gauge.assert_called_with("last_motion_age_sec", 0.0)
    assert payload["last_motion_at"] == ps.processor_status["last_motion_at"]
    assert payload["last_motion_age_sec"] == 0.0
