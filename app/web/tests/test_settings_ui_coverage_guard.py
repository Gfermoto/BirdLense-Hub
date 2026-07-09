"""Regression tests for scripts/check-settings-ui-coverage.py guardrails."""

from __future__ import annotations

import copy
import runpy
from pathlib import Path


_REPO_ROOT = next(
    (p for p in (Path(__file__).resolve().parents[3], Path("/workspace")) if (p / "scripts").exists()),
    Path(__file__).resolve().parents[3],
)
SCRIPT_PATH = _REPO_ROOT / "scripts" / "check-settings-ui-coverage.py"


def _load_checker_globals() -> dict:
    """Load checker module globals via runpy for direct function testing."""
    return runpy.run_path(str(SCRIPT_PATH))


def test_library_ui_guard_accepts_current_mapping():
    """Current allowlist must satisfy library-ui evidence guard."""
    g = _load_checker_globals()
    errors = g["_validate_library_ui_coverage"]()
    assert errors == []


def test_library_ui_guard_rejects_unmapped_key():
    """Guard must fail if a library-ui key is not represented in UI/API evidence."""
    g = _load_checker_globals()
    allowlist = g["ALLOWED_NON_UI_KEYS"]
    original = copy.deepcopy(allowlist)
    try:
        allowlist["video.__definitely_missing_ui_leaf__"] = {
            "category": "library-ui",
            "reason": "test",
            "next_step": "test",
        }
        errors = g["_validate_library_ui_coverage"]()
        assert any("video.__definitely_missing_ui_leaf__" in err for err in errors), errors
    finally:
        allowlist.clear()
        allowlist.update(original)


def test_tier_prefix_allowlist_covers_camera_role_presets():
    """Role preset subtree keys may be allowlisted by prefix (#623)."""
    g = _load_checker_globals()
    meta = g["_prefix_allowlist_meta"]("processor.camera_tuning_by_role.feeder_close.min_box_size_px")
    assert meta is not None
    assert meta["category"] == "advanced"


def test_tier_allowlist_categories_are_valid():
    """Expert/advanced allowlist entries must use known maturity categories."""
    g = _load_checker_globals()
    allowed_categories = {
        "derived",
        "legacy",
        "advanced",
        "ops-only",
        "planned-ui",
        "library-ui",
        "yaml-only",
        "backend-managed",
        "access-control",
    }
    for key, meta in g["ALLOWED_NON_UI_KEYS"].items():
        category = meta.get("category")
        assert category in allowed_categories, f"{key}: unknown category {category!r}"
