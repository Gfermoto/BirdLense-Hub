import os
import sys
import time
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
app_root = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.append(src_path)
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from decision_maker import DecisionMaker


def _make_track(
    *,
    detector_label='Bird',
    detector_confidences=None,
    classifier_events=None,
    start_time=0.0,
    end_time=2.0,
    frames=None,
    best_frame_score=0.0,
    key_frames=None,
):
    detector_confidences = detector_confidences or [0.9, 0.9, 0.9]
    classifier_events = classifier_events or []
    track = {
        'start_time': start_time,
        'end_time': end_time,
        'detector_events': [
            {'label': detector_label, 'confidence': conf, 't': idx * 0.1}
            for idx, conf in enumerate(detector_confidences)
        ],
        'classifier_events': [],
        'best_frame': None,
        'best_frame_score': best_frame_score,
        'key_frames': key_frames or [],
        'frames': frames or [],
    }
    for idx, row in enumerate(classifier_events):
        if isinstance(row, dict):
            track["classifier_events"].append(dict(row))
            continue
        name, cls_conf, det_conf = row[0], row[1], row[2]
        ev = {
            'species_name': name,
            'confidence': cls_conf,
            'detector_confidence': det_conf,
            'combined_confidence': det_conf * cls_conf,
            't': idx * 0.1,
        }
        if len(row) > 3:
            ev['entropy'] = row[3]
        if len(row) > 4:
            ev['top1_top2_margin'] = row[4]
        track['classifier_events'].append(ev)
    return track


class TestDecisionMaker(unittest.TestCase):
    def setUp(self):
        self.decision_maker = DecisionMaker(min_track_duration=0)

    def test_accepted_species_uses_classifier_evidence_only(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 10,
                classifier_events=[('Cardinal', 0.9, 0.9)] * 2,
            )
        }

        results = self.decision_maker.get_results(tracks)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Cardinal')
        self.assertAlmostEqual(results[0]['confidence'], 0.81)
        self.assertEqual(results[0]['decision_reason'], 'accepted_species')
        self.assertEqual(results[0]['primary_provider'], 'yolo')
        self.assertEqual(results[0]['primary_signal'], 'species_classifier')
        self.assertEqual(results[0]['threshold_path'], 'classifier_threshold')
        self.assertFalse(results[0]['fallback_used'])
        self.assertTrue(results[0]['yolo_track_present'])

    def test_classifier_majority_vote_uses_classifier_subset(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 10,
                classifier_events=(
                    [('Cardinal', 0.9, 0.9)] * 6
                    + [('Blue Jay', 0.8, 0.9)] * 4
                ),
            )
        }

        results = self.decision_maker.get_results(tracks)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Cardinal')
        self.assertAlmostEqual(results[0]['confidence'], 0.486)

    def test_species_confidence_overrides(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.10,
            species_confidence_overrides={"Rare Bird": 0.03},
        )
        tracks_rare = {
            1: _make_track(
                classifier_events=[('Rare Bird', 0.05, 1.0)] * 3,
            )
        }
        results = dm.get_results(tracks_rare)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Rare Bird')

        dm2 = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.10,
            species_confidence_overrides={"Rare Bird": 0.03},
        )
        tracks_common = {
            1: _make_track(
                classifier_events=[('Common Bird', 0.05, 1.0)] * 3,
                frames=[
                    {'t': 0.0, 'bbox': [0.10, 0.10, 0.30, 0.30]},
                    {'t': 0.1, 'bbox': [0.11, 0.11, 0.31, 0.31]},
                    {'t': 0.2, 'bbox': [0.12, 0.12, 0.32, 0.32]},
                ],
                best_frame_score=7.0,
            )
        }
        results2 = dm2.get_results(tracks_common)
        self.assertEqual(len(results2), 1)
        self.assertEqual(results2[0]['species_name'], 'Bird')
        self.assertEqual(results2[0]['decision_reason'], 'fallback_bird')

    def test_classifier_uncertain_emits_review_only_generic_bird_with_frames(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.5,
            min_confidence_to_store=0.25,
            classifier_fallback_bird=True,
        )
        tracks = {
            1: _make_track(
                detector_confidences=[0.35] * 5,
                classifier_events=[('Eurasian Jay', 1.0, 0.35)] * 5,
                frames=[{'t': 0.0, 'bbox': [0.1, 0.1, 0.2, 0.2]}],
            )
        }
        results = dm.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Bird')
        self.assertEqual(results[0]['decision_reason'], 'review_only_generic_bird')
        self.assertEqual(results[0]['decision_kind'], 'review_only_generic')
        self.assertFalse(results[0].get('visit_eligible', True))
        self.assertFalse(results[0].get('notification_eligible', True))
        self.assertEqual(results[0]['detector_label'], 'Bird')
        self.assertEqual(len(results[0].get('frames') or []), 1)
        self.assertTrue(results[0]['fallback_used'])
        self.assertEqual(results[0]['fallback_reason'], 'review_only_generic_bird')
        self.assertEqual(results[0]['primary_signal'], 'generic_visual_guard')
        self.assertEqual(results[0]['threshold_path'], 'classifier_threshold_then_generic_guard')

    def test_detector_only_weak_bird_is_review_only(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.5,
            min_confidence_to_store=0.25,
            classifier_fallback_bird=True,
        )
        tracks = {
            1: _make_track(
                detector_confidences=[0.35] * 5,
                classifier_events=[],
                frames=[{'t': 0.0, 'bbox': [0.1, 0.1, 0.2, 0.2]}],
            )
        }
        results = dm.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['decision_reason'], 'review_only_generic_bird')
        self.assertEqual(results[0]['decision_kind'], 'review_only_generic')

    def test_weak_detector_conf_accepted_with_detect_stream_defaults(self):
        """OV detect ~7 FPS: conf ~0.11 must not require generic_bird_min_detector_conf=0.42."""
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.20,
            min_confidence_to_store=0.08,
            generic_bird_min_detector_conf=0.10,
            generic_bird_min_frames=2,
            generic_bird_min_area_frac=0.006,
            generic_bird_min_best_frame_score=5.0,
        )
        tracks = {
            1: _make_track(
                detector_confidences=[0.11] * 3,
                classifier_events=[],
                frames=[
                    {"t": 0.0, "bbox": [0.10, 0.10, 0.19, 0.20]},
                    {"t": 0.1, "bbox": [0.11, 0.11, 0.20, 0.21]},
                ],
                best_frame_score=5.5,
            )
        }
        results = dm.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["decision_reason"], "fallback_bird")
        self.assertTrue(results[0].get("visit_eligible", True))

    def test_generic_bird_promotion_thresholds_are_configurable(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.5,
            min_confidence_to_store=0.25,
            generic_bird_min_detector_conf=0.40,
            generic_bird_min_frames=2,
            generic_bird_min_area_frac=0.008,
            generic_bird_min_best_frame_score=6.0,
        )
        tracks = {
            1: _make_track(
                detector_confidences=[0.42] * 4,
                classifier_events=[],
                frames=[
                    {'t': 0.0, 'bbox': [0.10, 0.10, 0.19, 0.20]},
                    {'t': 0.1, 'bbox': [0.11, 0.11, 0.20, 0.21]},
                ],
                best_frame_score=6.1,
            )
        }
        results = dm.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['decision_reason'], 'fallback_bird')
        self.assertTrue(results[0].get('visit_eligible', True))

    def test_classifier_uncertain_respects_fallback_off(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.5,
            min_confidence_to_store=0.25,
            classifier_fallback_bird=False,
        )
        tracks = {
            1: _make_track(
                detector_confidences=[0.35] * 5,
                classifier_events=[('Eurasian Jay', 1.0, 0.35)] * 5,
            )
        }
        self.assertEqual(len(dm.get_results(tracks)), 0)
        decisions = dm.get_decisions(tracks)
        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0]['accepted'])
        self.assertEqual(
            decisions[0]['decision_reason'],
            'rejected_classifier_fallback_disabled',
        )
        self.assertEqual(decisions[0]['reject_reason_code'], 'low_confidence')
        self.assertEqual(decisions[0]['trust_band'], 'red')

    def test_detector_only_rodent_fallback(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_store=0.20,
        )
        tracks = {
            1: _make_track(
                detector_label='Squirrel',
                detector_confidences=[0.42, 0.45, 0.40],
                classifier_events=[],
            )
        }
        results = dm.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Rodent')
        self.assertEqual(results[0]['decision_reason'], 'fallback_rodent')
        self.assertEqual(results[0]['detector_label'], 'Rodent')

    def test_detector_only_rodent_rejected_when_bbox_is_too_large(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_store=0.20,
            generic_rodent_min_frames=2,
            generic_rodent_max_area_frac=0.60,
        )
        tracks = {
            1: _make_track(
                detector_label='Rodent',
                detector_confidences=[0.52, 0.55, 0.50],
                classifier_events=[],
                frames=[
                    {'t': 0.1, 'bbox': [0.0, 0.0, 0.98, 0.98]},
                    {'t': 0.2, 'bbox': [0.01, 0.01, 0.97, 0.97]},
                ],
            )
        }
        self.assertEqual(dm.get_results(tracks), [])
        decisions = dm.get_decisions(tracks)
        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0]['accepted'])
        self.assertEqual(decisions[0]['decision_reason'], 'rejected_weak_generic_rodent')
        self.assertEqual(decisions[0]['reject_reason_code'], 'insufficient_frames')

    def test_species_confidence_overrides_match_scientific_common_labels(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.10,
            species_confidence_overrides={"House Sparrow": 0.03},
        )
        tracks = {
            1: _make_track(
                classifier_events=[('Passer domesticus (House Sparrow)', 0.05, 1.0)] * 3,
            )
        }

        results = dm.get_results(tracks)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['species_name'], 'Passer domesticus (House Sparrow)')

    def test_post_record_extends_inactive_window(self):
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
        # _effective_max_inactive = 1 + 5 = 6s; extra margin for CI / loaded runners
        time.sleep(6.0)
        self.assertTrue(dm.decide_stop_recording())

    def test_get_results_sorts_by_confidence_then_track_id(self):
        tracks = {
            9: _make_track(
                classifier_events=[('Blue Jay', 0.7, 1.0)] * 3,
            ),
            3: _make_track(
                classifier_events=[('Great Tit', 0.9, 1.0)] * 3,
            ),
            1: _make_track(
                classifier_events=[('Robin', 0.9, 1.0)] * 3,
            ),
        }

        results = self.decision_maker.get_results(tracks)

        self.assertEqual(
            [(item['track_id'], item['species_name']) for item in results],
            [(1, 'Robin'), (3, 'Great Tit'), (9, 'Blue Jay')],
        )

    def test_get_decisions_includes_rejected_short_track(self):
        dm = DecisionMaker(
            min_track_duration=5.0,
            min_confidence_to_store=0.25,
        )
        tracks = {
            7: _make_track(
                detector_confidences=[0.8] * 3,
                start_time=0.0,
                end_time=1.0,
            )
        }
        decisions = dm.get_decisions(tracks)
        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0]['accepted'])
        self.assertEqual(decisions[0]['decision_reason'], 'rejected_short_track')
        self.assertEqual(decisions[0]['trust_band'], 'red')

    def test_accepted_species_has_green_or_yellow_trust_band(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.95] * 3,
                classifier_events=[('Robin', 0.95, 0.95)] * 3,
            )
        }
        decisions = self.decision_maker.get_decisions(tracks)
        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0]['accepted'])
        self.assertEqual(decisions[0]['decision_reason'], 'accepted_species')
        self.assertEqual(decisions[0]['trust_band'], 'green')
        self.assertEqual(decisions[0]['outcome_bucket'], 'auto_accept')

    def test_decision_trace_includes_keyframe_and_vote_metadata(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 4,
                classifier_events=[('Robin', 0.8, 0.9)] * 3,
                best_frame_score=7.5,
                key_frames=[{'score': 7.5}, {'score': 6.0}],
            )
        }
        decisions = self.decision_maker.get_decisions(tracks)
        self.assertEqual(decisions[0]['key_frame_count'], 2)
        self.assertAlmostEqual(decisions[0]['best_frame_score'], 7.5)
        self.assertAlmostEqual(decisions[0]['classifier_vote_share'], 1.0)

    def test_rodent_species_uses_relaxed_threshold_vs_passerines(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.5,
            min_confidence_to_store=0.34,
        )
        rodent = {
            1: _make_track(
                detector_label='Rodent',
                detector_confidences=[0.6] * 4,
                classifier_events=[('Rodent', 0.9, 0.5)] * 4,
            )
        }
        self.assertEqual(
            dm.get_decisions(rodent)[0]['decision_reason'],
            'accepted_species',
        )
        bird = {
            1: _make_track(
                detector_label='Bird',
                detector_confidences=[0.6] * 4,
                classifier_events=[('Great Tit', 0.9, 0.5)] * 4,
            )
        }
        self.assertNotEqual(
            dm.get_decisions(bird)[0]['decision_reason'],
            'accepted_species',
        )

    def test_conflicting_classifier_votes_get_conflict_reject_code(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.8,
            min_confidence_to_store=0.9,
            classifier_fallback_bird=False,
        )
        tracks = {
            1: _make_track(
                detector_confidences=[0.4] * 4,
                classifier_events=[
                    ('Robin', 0.7, 0.5),
                    ('Blue Jay', 0.7, 0.5),
                    ('Robin', 0.7, 0.5),
                    ('Blue Jay', 0.7, 0.5),
                ],
            )
        }
        decisions = dm.get_decisions(tracks)
        self.assertEqual(decisions[0]['reject_reason_code'], 'conflicting_evidence')
        self.assertEqual(decisions[0]['trust_band'], 'gray')
        self.assertEqual(decisions[0]['decision_kind'], 'rejected')
        self.assertEqual(decisions[0]['outcome_bucket'], 'rejected')

    def test_review_only_generic_has_review_only_outcome_bucket(self):
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_store=0.3,
            generic_bird_min_detector_conf=0.9,
            generic_bird_min_frames=10,
            generic_bird_min_area_frac=0.8,
            generic_bird_min_best_frame_score=10.0,
        )
        tracks = {
            1: _make_track(
                detector_label='Bird',
                detector_confidences=[0.6] * 4,
                classifier_events=[],
                frames=[{'t': 0.0, 'bbox': [0.0, 0.0, 0.1, 0.1]}],
                best_frame_score=2.0,
            )
        }
        decisions = dm.get_decisions(tracks)
        self.assertTrue(decisions[0]['accepted'])
        self.assertFalse(decisions[0]['visit_eligible'])
        self.assertEqual(decisions[0]['decision_kind'], 'review_only_generic')
        self.assertEqual(decisions[0]['outcome_bucket'], 'review_only')

    @patch("app_config.app_config.app_config")
    def test_classifier_entropy_margin_and_needs_review(self, mock_cfg):
        def fake_get(k, default=None):
            if k == "processor.classifier_uncertainty_entropy_ge":
                return 1.5
            if k == "processor.classifier_uncertainty_margin_le":
                return 0.05
            return default

        mock_cfg.get.side_effect = fake_get
        dm = DecisionMaker(min_track_duration=0)
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 10,
                classifier_events=[
                    ("Cardinal", 0.9, 0.9, 2.0, 0.02),
                ],
            ),
        }
        d = dm.get_decisions(tracks)[0]
        self.assertAlmostEqual(d["classifier_entropy"], 2.0)
        self.assertAlmostEqual(d["classifier_top1_top2_margin"], 0.02)
        self.assertTrue(d["classifier_needs_review"])

if __name__ == '__main__':
    unittest.main()
