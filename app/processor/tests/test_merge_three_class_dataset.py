"""Smoke: scripts/datasets/merge_datasets_three_class.py (#367)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "datasets" / "merge_datasets_three_class.py"


def _touch(p: Path, content: bytes = b"x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


@pytest.mark.parametrize("make_test_split", [False, True])
def test_merge_three_class_builds_yaml(tmp_path: Path, make_test_split: bool) -> None:
    birds = tmp_path / "birds_binary_yolo"
    rod = tmp_path / "rodent_yolo"
    bg = tmp_path / "background_yolo"
    out = tmp_path / "out"

    for split in ("train", "val") + (("test",) if make_test_split else ()):
        _touch(birds / split / "images" / "b1.jpg")
        (birds / split / "labels").mkdir(parents=True, exist_ok=True)
        (birds / split / "labels" / "b1.txt").write_text(
            "0 0.5 0.5 0.2 0.2\n",
            encoding="utf-8",
        )
        _touch(rod / split / "images" / "r1.jpg")
        (rod / split / "labels").mkdir(parents=True, exist_ok=True)
        (rod / split / "labels" / "r1.txt").write_text(
            "1011 0.5 0.5 0.2 0.2\n",
            encoding="utf-8",
        )
        _touch(bg / split / "images" / "g1.jpg")
        # image-level negative: no label file

    cmd = [
        sys.executable,
        str(_SCRIPT),
        "--birds-dir",
        str(birds),
        "--rodent-dir",
        str(rod),
        "--background-dir",
        str(bg),
        "--output-dir",
        str(out),
    ]
    proc = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout

    ds = out / "dataset.yaml"
    assert ds.is_file()
    text = ds.read_text(encoding="utf-8")
    assert "Bird" in text and "Rodent" in text and "Background" in text

    train_lbl = out / "train" / "labels"
    assert (train_lbl / "b_b1.txt").read_text(encoding="utf-8").startswith("0 ")
    assert (train_lbl / "r_r1.txt").read_text(encoding="utf-8").startswith("1 ")
    assert (train_lbl / "g_g1.txt").read_text(encoding="utf-8").strip() == ""


def test_merge_import_no_syntax_error() -> None:
    spec = importlib.util.spec_from_file_location("merge_three", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.main)
