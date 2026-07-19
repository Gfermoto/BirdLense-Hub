"""RC1: RecognitionOutcome derivation from persist rows."""

from __future__ import annotations

import unittest

from recognition_outcome import OutcomeKind, from_persist_row, hub_taxonomy_wins


class TestRecognitionOutcome(unittest.TestCase):
    def test_hub_named_is_taxonomy_win(self):
        out = from_persist_row(
            {
                "species_name": "Parus major",
                "decision_kind": "accepted_species",
                "decision_reason": "accepted_classifier",
                "classifier_species_name": "Parus major",
                "detection_provider": "yolo",
            }
        )
        self.assertEqual(out.kind, OutcomeKind.NAMED_ACCEPT)
        self.assertTrue(out.hub_taxonomy_win)
        self.assertEqual(out.authority, "hub_classifier")

    def test_bird_generic_is_presence_not_named(self):
        out = from_persist_row(
            {
                "species_name": "Bird",
                "decision_kind": "accepted_species",
                "decision_reason": "accepted_binary_track_classifier_deferred",
                "classify_skip_reason": "deferred_budget",
                "detection_provider": "yolo",
            }
        )
        self.assertEqual(out.kind, OutcomeKind.PRESENCE)
        self.assertFalse(out.hub_taxonomy_win)

    def test_frigate_named_not_hub_win(self):
        out = from_persist_row(
            {
                "species_name": "Parus major",
                "decision_kind": "accepted_species",
                "decision_reason": "promoted_by_frigate",
                "frigate_species_promoted": True,
                "detection_provider": "frigate",
            }
        )
        self.assertEqual(out.kind, OutcomeKind.NAMED_ACCEPT)
        self.assertFalse(out.hub_taxonomy_win)
        self.assertEqual(out.authority, "frigate")

    def test_hub_taxonomy_wins_counts_only_hub(self):
        rows = [
            {
                "species_name": "Parus major",
                "decision_kind": "accepted_species",
                "classifier_species_name": "Parus major",
                "detection_provider": "yolo",
            },
            {
                "species_name": "Parus major",
                "decision_kind": "accepted_species",
                "frigate_species_promoted": True,
                "detection_provider": "frigate",
            },
            {
                "species_name": "Bird",
                "decision_kind": "accepted_generic",
                "decision_reason": "fallback_bird",
            },
            {
                # Stub named label without accept contract must not count.
                "species_name": "Parus major",
                "detection_provider": "yolo",
            },
        ]
        self.assertEqual(hub_taxonomy_wins(rows), 1)

    def test_stub_named_is_not_taxonomy_win(self):
        out = from_persist_row(
            {"species_name": "Parus major", "detection_provider": "yolo"}
        )
        self.assertEqual(out.kind, OutcomeKind.PRESENCE)
        self.assertFalse(out.hub_taxonomy_win)
        self.assertEqual(out.skip_reason, "named_without_accept_contract")

    def test_salvage_flag_keeps_hub_classifier_win(self):
        out = from_persist_row(
            {
                "species_name": "Parus major",
                "decision_kind": "accepted_species",
                "decision_reason": "accepted_classifier",
                "classifier_species_name": "Parus major",
                "detection_provider": "yolo",
                "frigate_trigger_salvage": True,
            }
        )
        self.assertEqual(out.kind, OutcomeKind.NAMED_ACCEPT)
        self.assertTrue(out.hub_taxonomy_win)
        self.assertEqual(out.authority, "hub_classifier")


if __name__ == "__main__":
    unittest.main()
