"""Тесты хелперов bootstrap_detector_yolo (seed shuffle / уникальное копирование)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS_DATASETS = Path(__file__).resolve().parents[3] / "scripts" / "datasets"
sys.path.insert(0, str(_SCRIPTS_DATASETS))

import bootstrap_detector_yolo as bd  # noqa: E402


@pytest.fixture
def restore_seed_env():
    key = "BIRDLENSE_BOOTSTRAP_BG_SEED_START"
    prev = os.environ.get(key)
    yield
    if prev is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = prev


def test_fiftyone_bg_shuffle_seed_env_override(tmp_path: Path, restore_seed_env) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    os.environ["BIRDLENSE_BOOTSTRAP_BG_SEED_START"] = "424242"
    assert bd._fiftyone_bg_shuffle_seed(tmp_path) == 424242


def test_fiftyone_bg_shuffle_seed_from_image_count(tmp_path: Path, restore_seed_env) -> None:
    os.environ.pop("BIRDLENSE_BOOTSTRAP_BG_SEED_START", None)
    for i in range(11):
        (tmp_path / f"f{i}.jpg").touch()
    assert bd._fiftyone_bg_shuffle_seed(tmp_path) == 11 % 982_451_653


@pytest.fixture
def restore_chunk_max_env():
    key = "BIRDLENSE_BOOTSTRAP_CHUNK_MAX"
    prev = os.environ.get(key)
    yield
    if prev is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = prev


def test_zoo_chunk_ceiling_default(restore_chunk_max_env) -> None:
    os.environ.pop("BIRDLENSE_BOOTSTRAP_CHUNK_MAX", None)
    assert bd._zoo_chunk_ceiling() == 960


def test_zoo_chunk_ceiling_env(restore_chunk_max_env) -> None:
    os.environ["BIRDLENSE_BOOTSTRAP_CHUNK_MAX"] = "64"
    assert bd._zoo_chunk_ceiling() == 64


def test_zoo_chunk_ceiling_bad_env_falls_back(restore_chunk_max_env) -> None:
    os.environ["BIRDLENSE_BOOTSTRAP_CHUNK_MAX"] = "nope"
    assert bd._zoo_chunk_ceiling() == 960


def test_unique_copy_collision_uses_hash_suffix(tmp_path: Path) -> None:
    src_a = tmp_path / "a"
    src_b = tmp_path / "b"
    dst_dir = tmp_path / "dst"
    src_a.mkdir()
    src_b.mkdir()
    dst_dir.mkdir()
    f_a = src_a / "same.jpg"
    f_b = src_b / "same.jpg"
    f_a.write_bytes(b"a")
    f_b.write_bytes(b"b")
    first = bd._unique_copy(f_a, dst_dir)
    assert first.name == "same.jpg"
    second = bd._unique_copy(f_b, dst_dir)
    assert second.name != "same.jpg"
    assert second.name.startswith("same_")
    assert second.suffix == ".jpg"
    assert second.read_bytes() == b"b"


def test_collect_no_bird_background_via_json(tmp_path: Path) -> None:
    root = tmp_path / "detector"
    bd._ensure_layout(root)
    inst = {
        "images": [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ],
        "categories": [
            {"id": 10, "name": "bird"},
            {"id": 20, "name": "person"},
        ],
        "annotations": [
            {"image_id": 1, "category_id": 10},
            {"image_id": 2, "category_id": 20},
        ],
    }
    jf = tmp_path / "instances.json"
    jf.write_text(json.dumps(inst), encoding="utf-8")
    data = tmp_path / "coco_data"
    data.mkdir()
    (data / "000000000002.jpg").write_bytes(b"x")
    (data / "000000000003.jpg").write_bytes(b"y")
    n = bd._collect_no_bird_background_via_json(
        root,
        coco_split="train",
        pool=50,
        target=10,
        out_tag="train",
        instances_json=jf,
        image_data_dir=data,
    )
    assert n == 2
    imgs = root / "binary" / "background" / "train" / "images"
    names = {p.name for p in imgs.iterdir()}
    assert "000000000002.jpg" in names
    assert "000000000003.jpg" in names


def test_collect_hard_negative_background_via_json(tmp_path: Path) -> None:
    root = tmp_path / "detector"
    bd._ensure_layout(root)
    inst = {
        "images": [{"id": 1}, {"id": 2}, {"id": 3}],
        "categories": [
            {"id": 10, "name": "bird"},
            {"id": 20, "name": "person"},
            {"id": 30, "name": "dog"},
        ],
        "annotations": [
            {"image_id": 1, "category_id": 10},
            {"image_id": 2, "category_id": 20},
            {"image_id": 3, "category_id": 30},
        ],
    }
    jf = tmp_path / "instances.json"
    jf.write_text(json.dumps(inst), encoding="utf-8")
    data = tmp_path / "coco_data"
    data.mkdir()
    (data / "000000000002.jpg").write_bytes(b"p")
    (data / "000000000003.jpg").write_bytes(b"d")
    n = bd._collect_hard_negative_background_via_json(
        root,
        coco_split="train",
        pool=50,
        target=10,
        out_tag="train",
        instances_json=jf,
        image_data_dir=data,
        trigger_labels=frozenset({"person", "dog"}),
    )
    assert n == 2
