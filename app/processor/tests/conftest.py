"""Pytest hooks: маркер ``heavy`` и env ``SKIP_HEAVY_PROCESSOR_TESTS`` (#282)."""

from __future__ import annotations

import os

import pytest

_TRUE = frozenset({'1', 'true', 'yes'})


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        'markers',
        'heavy: loads real ML weights or large assets; skipped if '
        'SKIP_HEAVY_PROCESSOR_TESTS=1 or when running with -m "not heavy"',
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if (os.environ.get('SKIP_HEAVY_PROCESSOR_TESTS') or '').strip().lower() not in _TRUE:
        return
    skip = pytest.mark.skip(
        reason='SKIP_HEAVY_PROCESSOR_TESTS=1 (see docs/TESTING.md)',
    )
    for item in items:
        if item.get_closest_marker('heavy'):
            item.add_marker(skip)
