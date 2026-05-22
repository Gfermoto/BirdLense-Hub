"""Tests for detector class_maps YAML → runtime allowlist."""

import os
import sys
import tempfile
from pathlib import Path

import yaml

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from detector_class_map import (  # noqa: E402
    resolve_allowed_class_ids,
    resolve_detector_scope_labels,
)


def test_trapper_map_only_bird_and_squirrel():
    map_file = (
        Path(__file__).resolve().parents[1]
        / "models/detection/class_maps/trapper_ai_v02_2024.yaml"
    )
    cfg = yaml.safe_load(map_file.read_text(encoding="utf-8"))
    allowed = resolve_allowed_class_ids(cfg)
    assert allowed == [0, 5]
    scope = resolve_detector_scope_labels(cfg, allowed)
    assert scope == ["Bird", "Eurasian Red Squirrel"]


def test_ignore_wins_over_class_to_scope():
    cfg = {
        "our_scope": ["bird", "squirrel"],
        "class_to_scope": {"bird": [0], "squirrel": [5, 10]},
        "ignore_class_ids": [10],
        "native_names": {0: "Bird", 5: "Sq", 10: "Hare"},
    }
    assert resolve_allowed_class_ids(cfg) == [0, 5]
