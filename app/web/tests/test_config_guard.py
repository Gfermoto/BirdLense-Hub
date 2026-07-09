"""Hub config guard (#492)."""

from __future__ import annotations

from app_config.config_guard import collect_merged_config_issues


def test_store_le_process_ordering():
    issues = collect_merged_config_issues(
        {
            "detection": {"min_confidence_to_store": 0.9},
            "processor": {"min_confidence_to_process": 0.2},
        },
    )
    assert any("min_confidence_to_store" in msg for msg in issues)
