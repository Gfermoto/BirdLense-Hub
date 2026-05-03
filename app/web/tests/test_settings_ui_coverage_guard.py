"""Regression tests for scripts/check-settings-ui-coverage.py guardrails."""

from __future__ import annotations

import copy
import runpy
from pathlib import Path


def _resolve_script_path() -> Path:
    """Resolve checker script path in host and docker test layouts."""
    candidates = [
        Path(__file__).resolve().parents[3] / "scripts" / "check-settings-ui-coverage.py",
        Path("/workspace/scripts/check-settings-ui-coverage.py"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "check-settings-ui-coverage.py was not found in known locations",
    )


SCRIPT_PATH = _resolve_script_path()


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
