"""Tests for ebird_regional_confidence merge (#128)."""
import unittest
from unittest.mock import patch


class _Cfg:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestMergeEbirdRegionalConfidence(unittest.TestCase):
    def test_disabled_returns_manual_only(self):
        from ebird_regional_confidence import (
            merge_species_confidence_overrides_with_ebird_top,
        )

        cfg = _Cfg(
            {
                'processor.ebird_regional_top_auto_confidence': False,
                'processor.species_confidence_overrides': {'A': 0.1},
                'secrets.ebird_api_key': 'x',
            }
        )
        out = merge_species_confidence_overrides_with_ebird_top(cfg)
        self.assertEqual(out, {'A': 0.1})

    def test_no_api_key_returns_manual_only(self):
        from ebird_regional_confidence import (
            merge_species_confidence_overrides_with_ebird_top,
        )

        cfg = _Cfg(
            {
                'processor.ebird_regional_top_auto_confidence': True,
                'processor.species_confidence_overrides': {'A': 0.1},
                'secrets.ebird_api_key': '',
            }
        )
        out = merge_species_confidence_overrides_with_ebird_top(cfg)
        self.assertEqual(out, {'A': 0.1})

    @patch('services.ebird_region_service.get_region_top_species_cached')
    @patch('services.ebird_region_service._build_region_code')
    def test_adds_mapped_top_not_overwriting_manual(
        self, mock_region, mock_top
    ):
        from ebird_regional_confidence import (
            merge_species_confidence_overrides_with_ebird_top,
        )

        mock_region.return_value = 'US-NY'
        mock_top.return_value = ['Blue Jay', 'Rare Manual']

        cfg = _Cfg(
            {
                'processor.ebird_regional_top_auto_confidence': True,
                'processor.species_confidence_overrides': {
                    'Rare Manual': 0.08,
                },
                'processor.min_confidence_to_process': 0.3,
                'processor.ebird_regional_top_confidence_delta': 0.05,
                'processor.ebird_regional_top_confidence_floor': 0.05,
                'secrets.ebird_api_key': 'test-key-128',
                'ebird.species_mapping': {},
            }
        )
        out = merge_species_confidence_overrides_with_ebird_top(cfg)
        self.assertEqual(out['Rare Manual'], 0.08)
        self.assertEqual(out['Blue Jay'], 0.25)
        mock_top.assert_called_once()
