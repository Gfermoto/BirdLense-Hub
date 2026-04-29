"""YOLO dataset label validation (#368)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[3]
    path = root / "scripts" / "datasets" / "validate_yolo_labels.py"
    spec = importlib.util.spec_from_file_location("validate_yolo_labels", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_validate_yolo_labels_reports_bad_class_and_bbox(tmp_path):
    mod = _load_module()
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "bad.txt").write_text("3 0.5 0.5 1.2 0.0\n", encoding="utf-8")

    report = mod.validate_labels(labels, class_count=3)

    assert report["ok"] is False
    assert report["error_count"] == 3
    assert any("class outside" in e for e in report["errors"])
    assert any("normalized" in e for e in report["errors"])
    assert any("width/height" in e for e in report["errors"])
