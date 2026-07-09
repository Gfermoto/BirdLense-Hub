"""ROI SR setup should warn when native model cannot load."""

from __future__ import annotations

import logging

from roi_super_resolution import RoiSuperResolution


def test_fsrcnn_missing_model_logs_warning(caplog):
    caplog.set_level(logging.WARNING)
    sr = RoiSuperResolution(
        {
            "experimental.sr_enabled": True,
            "experimental.sr_model": "fsrcnn_x2",
            "processor.models.sr_fsrcnn_x2_path": "/nonexistent/fsrcnn_x2.pb",
        }
    )
    assert sr._fsrcnn is None
    assert sr._native is False
    assert any("FSRCNN model not found" in rec.message for rec in caplog.records)
