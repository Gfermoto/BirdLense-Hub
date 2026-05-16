"""Tests for scripts/datasets/verify_hard_negatives_manifest.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'scripts' / 'datasets' / 'verify_hard_negatives_manifest.py'


def _load_mod():
    spec = importlib.util.spec_from_file_location(
        'verify_hard_negatives_manifest',
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _manifest(items):
    return {
        'schema': 'hard_negatives_manifest@v1',
        'items': items,
    }


def test_manifest_ok_structure_only():
    """Accept valid manifest without filesystem checks."""
    mod = _load_mod()
    ok, summary = mod.verify_manifest(
        _manifest(
            [
                {
                    'relative_path': (
                        'binary/background/train/images/bg_001.jpg'
                    ),
                    'kind': 'image_level',
                },
                {
                    'relative_path': (
                        'binary/background/val/images/crop_002.png'
                    ),
                    'kind': 'object_crop',
                },
            ],
        ),
        manifest_path=ROOT / 'tmp' / 'manifest.json',
        dataset_root=None,
        require_existing_files=False,
    )
    assert ok is True
    assert summary['errors'] == []


def test_manifest_fails_on_duplicates_and_kind():
    """Reject duplicate paths and unknown kinds."""
    mod = _load_mod()
    ok, summary = mod.verify_manifest(
        _manifest(
            [
                {
                    'relative_path': (
                        'binary/background/train/images/bg_001.jpg'
                    ),
                    'kind': 'image_level',
                },
                {
                    'relative_path': (
                        'binary/background/train/images/bg_001.jpg'
                    ),
                    'kind': 'bad_kind',
                },
            ],
        ),
        manifest_path=ROOT / 'tmp' / 'manifest.json',
        dataset_root=None,
        require_existing_files=False,
    )
    assert ok is False
    assert any('duplicate_relative_path:' in err for err in summary['errors'])


def test_manifest_fails_on_missing_file_when_required(tmp_path: Path):
    """Reject entries that cannot be resolved on disk."""
    mod = _load_mod()
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text('{}', encoding='utf-8')
    ok, summary = mod.verify_manifest(
        _manifest(
            [
                {
                    'relative_path': (
                        'binary/background/train/images/missing.jpg'
                    ),
                    'kind': 'image_level',
                },
            ],
        ),
        manifest_path=manifest_path,
        dataset_root=tmp_path / 'dataset',
        require_existing_files=True,
    )
    assert ok is False
    assert any('item_file_missing:' in err for err in summary['errors'])
