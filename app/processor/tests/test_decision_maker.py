
import unittest
import time
from unittest.mock import MagicMock
# Adjust import assuming running from project root
import sys
import os
# Ensure project root is in path to import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
# app/processor/tests -> app/processor/src
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)
from decision_maker import DecisionMaker

class TestDecisionMaker(unittest.TestCase):
    def setUp(self):
        self.decision_maker = DecisionMaker(min_track_duration=0)

    def test_combined_confidence_high_agreement_high_conf(self):
        """
        Test case: High voting agreement, high classifier confidence.
        """
        tracks = {
            1: {
                'start_time': time.time(),
                'end_time': time.time() + 1,
                'preds': [('Cardinal', 0.9)] * 10,
                'best_frame': None
            }
        }
        
        results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Cardinal')
        self.assertAlmostEqual(results[0]['confidence'], 0.9)

    def test_combined_confidence_high_agreement_low_conf(self):
        """
        Test case: High voting agreement, low classifier confidence.
        """
        tracks = {
            1: {
                'start_time': time.time(),
                'end_time': time.time() + 1,
                'preds': [('Cardinal', 0.4)] * 10,
                'best_frame': None
            }
        }
        
        results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Cardinal')
        self.assertAlmostEqual(results[0]['confidence'], 0.4)

    def test_combined_confidence_mixed_voting(self):
        """
        Test case: Mixed voting.
        """
        preds = [('Cardinal', 0.9)] * 6 + [('Blue Jay', 0.8)] * 4
        tracks = {
            1: {
                'start_time': time.time(),
                'end_time': time.time() + 1,
                'preds': preds,
                'best_frame': None
            }
        }
        
        results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Cardinal')
        # 0.6 * 0.9 = 0.54
        self.assertAlmostEqual(results[0]['confidence'], 0.54)

    def test_combined_confidence_mixed_voting_variable_conf(self):
        """
        Test case: Mixed voting with variable confidence.
        """
        preds = [('Cardinal', 0.9)] * 3 + [('Cardinal', 0.5)] * 3 + [('Blue Jay', 0.8)] * 4
        tracks = {
            1: {
                'start_time': time.time(),
                'end_time': time.time() + 1,
                'preds': preds,
                'best_frame': None
            }
        }
        
        results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Cardinal')
        # Voting: 0.6. Avg Conf: (2.7 + 1.5)/6 = 0.7. Result: 0.42
        self.assertAlmostEqual(results[0]['confidence'], 0.42)

    def test_species_confidence_overrides(self):
        """
        Test case: species_confidence_overrides lowers threshold for specific species.
        """
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.10,
            species_confidence_overrides={"Rare Bird": 0.03},
        )
        # Rare Bird with 0.05 confidence: passes (0.05 >= 0.03)
        tracks_rare = {
            1: {
                'start_time': time.time(),
                'end_time': time.time() + 1,
                'preds': [('Rare Bird', 0.05)] * 10,
                'best_frame': None,
            }
        }
        results = dm.get_results(tracks_rare)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Rare Bird')

        # Common Bird with 0.05 confidence: filtered (0.05 < 0.10)
        dm2 = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.10,
            species_confidence_overrides={"Rare Bird": 0.03},
        )
        tracks_common = {
            1: {
                'start_time': time.time(),
                'end_time': time.time() + 1,
                'preds': [('Common Bird', 0.05)] * 10,
                'best_frame': None,
            }
        }
        results2 = dm2.get_results(tracks_common)
        self.assertEqual(len(results2), 0)

    def test_post_record_extends_inactive_window(self):
        """post_record_seconds adds to max_inactive before stop (#157)."""
        dm = DecisionMaker(
            max_record_seconds=3600,
            max_inactive_seconds=1,
            post_record_seconds=5,
            min_track_duration=0,
        )
        dm.update_has_detections(False)
        self.assertFalse(dm.decide_stop_recording())
        time.sleep(1.2)
        self.assertFalse(dm.decide_stop_recording())
        time.sleep(5.1)
        self.assertTrue(dm.decide_stop_recording())

if __name__ == '__main__':
    unittest.main()
