"""Tests for BirdNET MQTT classifier bias (#129)."""
import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from birdnet_mqtt_confidence import merge_birdnet_mqtt_bias_into_overrides


class TestBirdnetMqttConfidence(unittest.TestCase):
    def test_disabled_returns_base(self):
        agg = MagicMock()
        cfg = {'processor.birdnet_mqtt_auto_confidence': False}
        base = {'A': 0.1}
        self.assertEqual(
            merge_birdnet_mqtt_bias_into_overrides(base, cfg, agg),
            base,
        )

    def test_no_aggregator(self):
        cfg = {'processor.birdnet_mqtt_auto_confidence': True}
        base = {'A': 0.1}
        self.assertEqual(
            merge_birdnet_mqtt_bias_into_overrides(base, cfg, None),
            base,
        )

    def test_adds_species_from_recent_birdnet(self):
        agg = MagicMock()
        agg.get_birdnet_prior_scores.return_value = {
            'Great Tit': {'score': 1.0, 'support_count': 1}
        }

        cfg = {
            'processor.birdnet_mqtt_auto_confidence': True,
            'processor.min_confidence_to_process': 0.3,
            'processor.birdnet_mqtt_bias_delta': 0.05,
            'processor.birdnet_mqtt_bias_floor': 0.05,
            'processor.birdnet_mqtt_prior_window_hours': 24,
            'processor.birdnet_mqtt_prior_ttl_hours': 25,
            'processor.birdnet_mqtt_prior_half_life_hours': 6,
            'detection.species_mapping': {},
        }
        out = merge_birdnet_mqtt_bias_into_overrides({}, cfg, agg)
        self.assertIn('Great tit', out)
        self.assertAlmostEqual(out['Great tit'], 0.25)

    def test_manual_override_preserved(self):
        agg = MagicMock()
        agg.get_birdnet_prior_scores.return_value = {
            'Great Tit': {'score': 1.0, 'support_count': 1}
        }
        cfg = {
            'processor.birdnet_mqtt_auto_confidence': True,
            'processor.min_confidence_to_process': 0.3,
            'detection.species_mapping': {},
        }
        base = {'Great Tit': 0.08}
        out = merge_birdnet_mqtt_bias_into_overrides(base, cfg, agg)
        self.assertEqual(out['Great Tit'], 0.08)

    def test_prior_score_scales_threshold_reduction(self):
        agg = MagicMock()
        agg.get_birdnet_prior_scores.return_value = {
            'Great Tit': {'score': 0.4, 'support_count': 1}
        }
        cfg = {
            'processor.birdnet_mqtt_auto_confidence': True,
            'processor.min_confidence_to_process': 0.3,
            'processor.birdnet_mqtt_bias_delta': 0.05,
            'processor.birdnet_mqtt_bias_floor': 0.05,
            'detection.species_mapping': {},
        }
        out = merge_birdnet_mqtt_bias_into_overrides({}, cfg, agg)
        self.assertAlmostEqual(out['Great tit'], 0.28)

    def test_deprecated_window_seconds_alias_used_when_hours_missing(self):
        agg = MagicMock()
        agg.get_birdnet_prior_scores.return_value = {}
        cfg = {
            'processor.birdnet_mqtt_auto_confidence': True,
            'processor.birdnet_mqtt_bias_window_seconds': 7200,
            'detection.species_mapping': {},
        }
        merge_birdnet_mqtt_bias_into_overrides({}, cfg, agg)
        kwargs = agg.get_birdnet_prior_scores.call_args.kwargs
        self.assertAlmostEqual(float(kwargs.get('window_hours')), 2.0)


if __name__ == '__main__':
    unittest.main()
