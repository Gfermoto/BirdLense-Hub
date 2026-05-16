"""Tests for scripts/datasets/import_roboflow_bird_feeder_birds.py."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / 'scripts' / 'datasets' / 'import_roboflow_bird_feeder_birds.py'


def _load_mod():
    spec = importlib.util.spec_from_file_location('import_roboflow_bf', _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_find_roboflow_yolo_export_root_flat(tmp_path: Path) -> None:
    mod = _load_mod()
    base = tmp_path / 'out'
    (base / 'train' / 'images').mkdir(parents=True)
    assert mod.find_roboflow_yolo_export_root(base) == base


def test_find_roboflow_yolo_export_root_nested(tmp_path: Path) -> None:
    mod = _load_mod()
    nested = tmp_path / 'Bird-Feeder-3'
    (nested / 'train' / 'images').mkdir(parents=True)
    assert mod.find_roboflow_yolo_export_root(tmp_path) == nested


def test_import_roboflow_extracted_dir(tmp_path: Path) -> None:
    """Импорт из распакованной папки (--extracted-dir)."""
    import subprocess
    import sys

    inner = tmp_path / 'proj'
    (inner / 'train' / 'images').mkdir(parents=True)
    (inner / 'train' / 'labels').mkdir(parents=True)
    (inner / 'valid' / 'images').mkdir(parents=True)
    (inner / 'valid' / 'labels').mkdir(parents=True)
    (inner / 'train' / 'images' / 'x.jpg').write_bytes(b'\xff\xd8\xff\xd9')
    (inner / 'train' / 'labels' / 'x.txt').write_text(
        '2 0.5 0.5 0.2 0.2\n',
        encoding='utf-8',
    )
    (inner / 'valid' / 'images' / 'y.jpg').write_bytes(b'\xff\xd8\xff\xd9')
    (inner / 'valid' / 'labels' / 'y.txt').write_text(
        '1 0.3 0.3 0.1 0.1\n',
        encoding='utf-8',
    )

    detector_root = tmp_path / 'detector'
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            '--root',
            str(detector_root),
            '--extracted-dir',
            str(inner),
            '--prefix',
            'ex_',
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    train_lbl = detector_root / 'binary' / 'birds' / 'train' / 'labels' / 'ex_x.txt'
    assert train_lbl.read_text(encoding='utf-8').startswith('0 ')


def test_import_roboflow_zip_to_detector_root(tmp_path: Path) -> None:
    """Мини-ZIP в стиле Roboflow → binary/birds/train и val."""
    import subprocess
    import sys

    inner = tmp_path / 'proj'
    (inner / 'train' / 'images').mkdir(parents=True)
    (inner / 'train' / 'labels').mkdir(parents=True)
    (inner / 'valid' / 'images').mkdir(parents=True)
    (inner / 'valid' / 'labels').mkdir(parents=True)
    img_t = inner / 'train' / 'images' / 'a.jpg'
    img_t.write_bytes(b'\xff\xd8\xff\xd9')
    (inner / 'train' / 'labels' / 'a.txt').write_text(
        '3 0.5 0.5 0.2 0.2\n',
        encoding='utf-8',
    )
    img_v = inner / 'valid' / 'images' / 'b.jpg'
    img_v.write_bytes(b'\xff\xd8\xff\xd9')
    (inner / 'valid' / 'labels' / 'b.txt').write_text(
        '1 0.4 0.4 0.1 0.1\n',
        encoding='utf-8',
    )

    zpath = tmp_path / 'export.zip'
    with zipfile.ZipFile(zpath, 'w') as zf:
        for p in inner.rglob('*'):
            if p.is_file():
                zf.write(p, p.relative_to(inner.parent))

    detector_root = tmp_path / 'detector'
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            '--root',
            str(detector_root),
            '--zip',
            str(zpath),
            '--prefix',
            't_',
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout

    train_lbl = detector_root / 'binary' / 'birds' / 'train' / 'labels' / 't_a.txt'
    assert train_lbl.read_text(encoding='utf-8').startswith('0 ')
    val_lbl = detector_root / 'binary' / 'birds' / 'val' / 'labels' / 't_b.txt'
    assert val_lbl.is_file()
    assert val_lbl.read_text(encoding='utf-8').startswith('0 ')


def test_import_roboflow_binary_subdir_rodent(tmp_path: Path) -> None:
    """--binary-subdir rodent → binary/rodent/…"""
    import subprocess
    import sys

    inner = tmp_path / 'proj'
    (inner / 'train' / 'images').mkdir(parents=True)
    (inner / 'train' / 'labels').mkdir(parents=True)
    (inner / 'valid' / 'images').mkdir(parents=True)
    (inner / 'valid' / 'labels').mkdir(parents=True)
    (inner / 'train' / 'images' / 'r.jpg').write_bytes(b'\xff\xd8\xff\xd9')
    (inner / 'train' / 'labels' / 'r.txt').write_text(
        '5 0.5 0.5 0.2 0.2\n',
        encoding='utf-8',
    )
    (inner / 'valid' / 'images' / 's.jpg').write_bytes(b'\xff\xd8\xff\xd9')
    (inner / 'valid' / 'labels' / 's.txt').write_text(
        '2 0.4 0.4 0.1 0.1\n',
        encoding='utf-8',
    )

    detector_root = tmp_path / 'detector'
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            '--root',
            str(detector_root),
            '--extracted-dir',
            str(inner),
            '--binary-subdir',
            'rodent',
            '--prefix',
            'rod_',
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    lbl = detector_root / 'binary' / 'rodent' / 'train' / 'labels' / 'rod_r.txt'
    assert lbl.read_text(encoding='utf-8').startswith('0 ')
