"""Юнит-тесты для ``heavy_skip`` (#282)."""

from __future__ import annotations

import os
import unittest

import heavy_skip


class TestHeavySkipEnv(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop('SKIP_HEAVY_PROCESSOR_TESTS', None)

    def test_false_when_unset(self) -> None:
        os.environ.pop('SKIP_HEAVY_PROCESSOR_TESTS', None)
        self.assertFalse(heavy_skip.skip_heavy_processor_tests_requested())

    def test_true_for_one_true_yes(self) -> None:
        for v in ('1', 'true', 'YES'):
            os.environ['SKIP_HEAVY_PROCESSOR_TESTS'] = v
            self.assertTrue(
                heavy_skip.skip_heavy_processor_tests_requested(),
                msg=v,
            )

    def test_maybe_skip_raises_skip_test(self) -> None:
        os.environ['SKIP_HEAVY_PROCESSOR_TESTS'] = '1'
        with self.assertRaises(unittest.SkipTest):
            heavy_skip.maybe_skip_heavy(self)
