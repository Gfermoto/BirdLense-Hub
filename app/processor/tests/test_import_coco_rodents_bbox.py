"""Нормализация COCO bbox → YOLO для import_coco_rodents_to_binary."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_mod():
    p = Path(__file__).resolve().parents[3] / "scripts" / "datasets" / "import_coco_rodents_to_binary.py"
    spec = importlib.util.spec_from_file_location("import_coco_rodents", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_coco_bbox_to_yolo_center_and_size():
    m = _load_mod()
    line = m.coco_bbox_pixels_to_yolo_line([0.0, 0.0, 100.0, 100.0], 200, 200)
    assert line is not None
    parts = line.strip().split()
    assert parts[0] == "0"
    assert tuple(round(float(x), 6) for x in parts[1:]) == (0.25, 0.25, 0.5, 0.5)


def test_coco_bbox_rejects_tiny_box():
    m = _load_mod()
    assert m.coco_bbox_pixels_to_yolo_line([0.0, 0.0, 1.0, 40.0], 100, 100) is None
