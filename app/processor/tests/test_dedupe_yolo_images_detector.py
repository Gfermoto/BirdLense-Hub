"""Тест глобального дедупа для merge_datasets_three_class (b_/r_/g_)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DATASETS = Path(__file__).resolve().parents[3] / "scripts" / "datasets"
sys.path.insert(0, str(_SCRIPTS_DATASETS))

import dedupe_yolo_images as dy  # noqa: E402


def test_detector_merge_global_keeps_bird_prefix_over_g(tmp_path: Path) -> None:
    root = tmp_path / "yolo"
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "labels").mkdir(parents=True)
    blob = b"\xff\xd8\xff\xe0samejpegbytes"
    (root / "train" / "images" / "g_z.jpg").write_bytes(blob)
    (root / "train" / "images" / "b_z.jpg").write_bytes(blob)
    (root / "train" / "labels" / "g_z.txt").write_text("", encoding="utf-8")
    (root / "train" / "labels" / "b_z.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")

    rep = dy._dedupe_detector_merge_global(root, dry_run=False, merge_scope="global")
    assert rep["duplicate_groups"] == 1
    assert len(list((root / "train" / "images").iterdir())) == 1
    kept = next((root / "train" / "images").iterdir())
    assert kept.name.startswith("b_")


def test_detector_merge_source_aware_keeps_coco_over_cub_same_bytes(tmp_path: Path) -> None:
    """При одинаковых байтах b_* оставляем COCO (12 digit), не CUB."""
    root = tmp_path / "yolo"
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "labels").mkdir(parents=True)
    blob = b"\xff\xd8\xff\xe0samebirdbytes"
    (root / "train" / "images" / "b_000000000001.jpg").write_bytes(blob)
    (root / "train" / "images" / "b_cub_00001_Foo_0001.jpg").write_bytes(blob)
    (root / "train" / "labels" / "b_000000000001.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (root / "train" / "labels" / "b_cub_00001_Foo_0001.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    rep = dy._dedupe_detector_merge_global(
        root, dry_run=False, merge_strategy="source-aware", merge_scope="within-prefix"
    )
    assert rep["duplicate_groups"] == 1
    kept = list((root / "train" / "images").iterdir())
    assert len(kept) == 1
    assert kept[0].name == "b_000000000001.jpg"


def test_within_prefix_same_bytes_bird_and_bg_both_kept(tmp_path: Path) -> None:
    """Одинаковые байты у b_ и g_ — оба остаются (дефолтный scope)."""
    root = tmp_path / "yolo"
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "labels").mkdir(parents=True)
    blob = b"\xff\xd8\xff\xe0pixsame"
    (root / "train" / "images" / "g_zz.jpg").write_bytes(blob)
    (root / "train" / "images" / "b_zz.jpg").write_bytes(blob)
    (root / "train" / "labels" / "g_zz.txt").write_text("", encoding="utf-8")
    (root / "train" / "labels" / "b_zz.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")

    rep = dy._dedupe_detector_merge_global(root, dry_run=False, merge_scope="within-prefix")
    assert rep["duplicate_groups"] == 0
    assert len(list((root / "train" / "images").iterdir())) == 2


def test_detector_merge_global_train_over_val_same_prefix(tmp_path: Path) -> None:
    root = tmp_path / "yolo"
    blob = b"\xff\xd8\xff\xe0same2"
    for sp in ("train", "val"):
        (root / sp / "images").mkdir(parents=True)
        (root / sp / "labels").mkdir(parents=True)
        (root / sp / "images" / "g_a.jpg").write_bytes(blob)
        (root / sp / "labels" / "g_a.txt").write_text("", encoding="utf-8")

    rep = dy._dedupe_detector_merge_global(root, dry_run=False, merge_scope="global")
    assert rep["duplicate_groups"] == 1
    assert (root / "train" / "images" / "g_a.jpg").is_file()
    assert not (root / "val" / "images" / "g_a.jpg").exists()
