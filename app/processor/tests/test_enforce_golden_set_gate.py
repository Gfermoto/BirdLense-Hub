"""Tests for scripts/enforce_golden_set_gate.py (#534)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "enforce_golden_set_gate.py"
    spec = importlib.util.spec_from_file_location(
        "enforce_golden_set_gate",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["enforce_golden_set_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_requires_gate_for_model_change():
    mod = _load_mod()
    required, trigger = mod.requires_golden_gate(
        ["app/processor/models/detection/weights/best.pt"]
    )
    assert required is True
    assert "app/processor/models/detection/weights/best.pt" in trigger


def test_requires_gate_for_detection_config_change():
    mod = _load_mod()
    required, trigger = mod.requires_golden_gate(
        ["app/app_config/default_config.yaml"]
    )
    assert required is True
    assert trigger == ["app/app_config/default_config.yaml"]


def test_skips_for_non_ml_docs_change():
    mod = _load_mod()
    required, trigger = mod.requires_golden_gate(
        ["docs/contributor/testing.md"]
    )
    assert required is False
    assert trigger == []
