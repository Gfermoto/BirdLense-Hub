"""Tests for shared.frame_shape parsers."""

from __future__ import annotations

import numpy as np
import pytest

from shared.frame_shape import (
    hw_to_wh,
    metadata_hw_list,
    numpy_hw,
    parse_config_wh,
    parse_metadata_hw,
    playback_hw_matches_main_size,
    probe_wh,
    shapes_hw_equal,
    wh_to_hw,
)


def test_parse_metadata_hw_height_width_order():
    assert parse_metadata_hw([720, 1280]) == (720, 1280)
    assert parse_metadata_hw([1520, 2688]) == (1520, 2688)
    assert parse_metadata_hw([0, 720]) is None
    assert parse_metadata_hw("bad") is None


def test_parse_config_wh_width_height_order():
    assert parse_config_wh([1280, 720]) == (1280, 720)
    assert parse_config_wh({"width": 704, "height": 576}) == (704, 576)


def test_numpy_hw_from_frame():
    frame = np.zeros((576, 704, 3), dtype=np.uint8)
    assert numpy_hw(frame) == (576, 704)


def test_probe_wh_main_size():
    assert probe_wh((1920, 1080)) == (1920, 1080)
    assert probe_wh([2688, 1520]) == (2688, 1520)
    assert wh_to_hw((2688, 1520)) == (1520, 2688)
    assert hw_to_wh((1520, 2688)) == (2688, 1520)


def test_playback_hw_matches_main_size():
    assert playback_hw_matches_main_size((1080, 1920), (1920, 1080))
    assert not playback_hw_matches_main_size((720, 1280), (1920, 1080))


def test_metadata_hw_list_roundtrip():
    hw = (480, 848)
    assert parse_metadata_hw(metadata_hw_list(hw)) == hw


def test_shapes_hw_equal():
    assert shapes_hw_equal((720, 1280), [720, 1280])
    assert not shapes_hw_equal((720, 1280), (1080, 1920))
