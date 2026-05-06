"""Smoke: scripts/datasets/convert_cub_to_yolo.py — CUB → binary/birds YOLO."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / 'scripts' / 'datasets' / 'convert_cub_to_yolo.py'


@pytest.fixture
def minimal_cub(tmp_path: Path) -> Path:
    """Минимальное дерево CUB для одного изображения (размеры из image_sizes.txt)."""
    cub = tmp_path / 'CUB_200_2011'
    img_dir = cub / 'images' / '001.Test_species'
    img_dir.mkdir(parents=True)
    img_path = img_dir / 'test_bird_001.jpg'
    img_path.write_bytes(b'\xff\xd8\xff\xd9')

    (cub / 'images.txt').write_text(
        '1 001.Test_species/test_bird_001.jpg\n',
        encoding='utf-8',
    )
    (cub / 'bounding_boxes.txt').write_text(
        '1 10 10 50 40\n',
        encoding='utf-8',
    )
    (cub / 'train_test_split.txt').write_text('1 1\n', encoding='utf-8')
    (cub / 'image_sizes.txt').write_text('1 100 80\n', encoding='utf-8')
    return cub


def test_convert_cub_writes_yolo_label(minimal_cub: Path, tmp_path: Path) -> None:
    """Скрипт кладёт один train-пример с классом 0."""
    detector_root = tmp_path / 'detector'
    cmd = [
        sys.executable,
        str(_SCRIPT),
        '--root',
        str(detector_root),
        '--cub-root',
        str(minimal_cub),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout

    train_lbl = detector_root / 'binary' / 'birds' / 'train' / 'labels'
    lbl = train_lbl / 'cub_00001_test_bird_001.txt'
    assert lbl.is_file()
    parts = lbl.read_text(encoding='utf-8').strip().split()
    assert parts[0] == '0'
    assert len(parts) == 5


def test_convert_import_no_syntax_error() -> None:
    spec = importlib.util.spec_from_file_location('convert_cub', _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.main)
