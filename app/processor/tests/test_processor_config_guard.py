"""Processor strict config guard (#492)."""

from __future__ import annotations

import pytest

from app_config.config_guard import collect_merged_config_issues, strict_config_enabled


def test_strict_enabled_for_processor_by_default(monkeypatch):
    monkeypatch.delenv("BIRDLENSE_STRICT_CONFIG", raising=False)
    monkeypatch.delenv("BIRDLENSE_PROCESSOR_STRICT_CONFIG", raising=False)
    assert strict_config_enabled(for_processor=True) is True


def test_invalid_processor_binary_imgsz_rejected():
    issues = collect_merged_config_issues(
        {
            "processor": {"binary_imgsz": -1},
            "detection": {"min_confidence_to_store": 0.05},
        },
    )
    assert any("binary_imgsz" in msg or "processor" in msg for msg in issues)
