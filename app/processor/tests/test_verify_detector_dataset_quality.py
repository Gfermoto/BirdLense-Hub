"""Tests for scripts/datasets/verify_detector_dataset_quality.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'scripts' / 'datasets' / 'verify_detector_dataset_quality.py'


def _load_mod():
    spec = importlib.util.spec_from_file_location(
        'verify_detector_dataset_quality',
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _profile() -> dict[str, object]:
    return {
        'dataset_root': '/tmp/ds',
        'classes': {
            'birds': {
                'train': {
                    'images': 500,
                    'labels': 500,
                    'source_tags': {'nabirds': 300, 'coco': 200},
                },
                'val': {
                    'images': 100,
                    'labels': 100,
                    'source_tags': {'nabirds': 60, 'coco': 40},
                },
            },
            'rodent': {
                'train': {
                    'images': 180,
                    'labels': 180,
                    'source_tags': {'oid': 120, 'github': 60},
                },
                'val': {
                    'images': 40,
                    'labels': 40,
                    'source_tags': {'oid': 30, 'github': 10},
                },
            },
            'background': {
                'train': {
                    'images': 160,
                    'labels': 160,
                    'source_tags': {'coco': 160},
                },
                'val': {
                    'images': 32,
                    'labels': 32,
                    'source_tags': {'coco': 32},
                },
            },
        },
    }


def test_quality_ok():
    """Verify quality gates pass on healthy profile."""
    mod = _load_mod()
    ok, summary = mod.verify_quality(
        _profile(),
        min_train={'birds': 300, 'rodent': 120, 'background': 120},
        min_val={'birds': 60, 'rodent': 24, 'background': 24},
        max_train_imbalance_ratio=8.0,
        min_source_tags={'birds': 2, 'rodent': 2, 'background': 1},
        max_unknown_tag_share=0.35,
        min_background_share_train=0.10,
        max_background_share_train=0.60,
    )
    assert ok is True
    assert summary['ok'] is True
    assert summary['errors'] == []


def test_quality_fails_on_parity_and_imbalance():
    """Fail when label parity breaks and train split is highly imbalanced."""
    mod = _load_mod()
    profile = _profile()
    profile['classes']['rodent']['train']['labels'] = 120
    profile['classes']['background']['train']['images'] = 40
    ok, summary = mod.verify_quality(
        profile,
        min_train={'birds': 300, 'rodent': 120, 'background': 120},
        min_val={'birds': 60, 'rodent': 24, 'background': 24},
        max_train_imbalance_ratio=6.0,
        min_source_tags={'birds': 2, 'rodent': 2, 'background': 1},
        max_unknown_tag_share=0.35,
        min_background_share_train=0.10,
        max_background_share_train=0.60,
    )
    assert ok is False
    assert any(
        'label_image_parity_failed:rodent:train' in err
        for err in summary['errors']
    )
    assert any(
        'train_images_below_min:background' in err for err in summary['errors']
    )
    assert any('train_imbalance_ratio_high' in err for err in summary['errors'])


def test_quality_fails_on_unknown_source_share():
    """Fail when unknown source tags dominate a split."""
    mod = _load_mod()
    profile = _profile()
    profile['classes']['birds']['val']['source_tags'] = {
        'unknown': 80,
        'coco': 20,
    }
    ok, summary = mod.verify_quality(
        profile,
        min_train={'birds': 300, 'rodent': 120, 'background': 120},
        min_val={'birds': 60, 'rodent': 24, 'background': 24},
        max_train_imbalance_ratio=8.0,
        min_source_tags={'birds': 2, 'rodent': 2, 'background': 1},
        max_unknown_tag_share=0.35,
        min_background_share_train=0.10,
        max_background_share_train=0.60,
    )
    assert ok is False
    assert any(
        'unknown_source_share_high:birds:val' in err
        for err in summary['errors']
    )
