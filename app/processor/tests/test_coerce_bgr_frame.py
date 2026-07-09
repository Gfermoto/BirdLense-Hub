"""Tests for classification-frame coercion before crop/cls."""

from __future__ import annotations

import numpy as np
import pytest

from detection_strategy import coerce_bgr_frame


def test_coerce_accepts_valid_bgr_uint8():
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    out = coerce_bgr_frame(frame)
    assert out is not None
    assert out.shape == (64, 64, 3)
    assert out.dtype == np.uint8


def test_coerce_rejects_invalid_types():
    assert coerce_bgr_frame([1, 2, 3]) is None
    assert coerce_bgr_frame(np.zeros((8, 8, 5))) is None
    assert coerce_bgr_frame(np.zeros((4, 4, 3), dtype=np.uint8)) is None


def test_coerce_grayscale_to_bgr():
    gray = np.full((32, 32), 128, dtype=np.uint8)
    out = coerce_bgr_frame(gray)
    assert out is not None
    assert out.shape == (32, 32, 3)
