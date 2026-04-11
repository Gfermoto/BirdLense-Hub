"""Пропуск «тяжёлых» processor-тестов (YOLO + реальные веса) при нехватке RAM (#282)."""

from __future__ import annotations

import os
import unittest

_TRUE = frozenset({'1', 'true', 'yes'})


def skip_heavy_processor_tests_requested() -> bool:
    """``SKIP_HEAVY_PROCESSOR_TESTS=1`` / ``true`` / ``yes`` (регистронезависимо)."""
    return (os.environ.get('SKIP_HEAVY_PROCESSOR_TESTS') or '').strip().lower() in _TRUE


def maybe_skip_heavy(case: unittest.TestCase) -> None:
    """Вызвать в начале тяжёлого ``unittest``-метода: ``maybe_skip_heavy(self)``."""
    if skip_heavy_processor_tests_requested():
        case.skipTest(
            'SKIP_HEAVY_PROCESSOR_TESTS is set (see docs/TESTING.md)',
        )
