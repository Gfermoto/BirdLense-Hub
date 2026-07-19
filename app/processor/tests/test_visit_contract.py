"""Visit quality contract + Frigate species authority."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from visit_contract import (
    apply_frigate_named_accept,
    compute_visit_quality,
    frigate_species_authority,
    is_frigate_promoteable_reason,
    is_frigate_sourced_row,
    is_named_product_species,
    role_detection_flag,
)


class _Cfg:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestVisitContract(unittest.TestCase):
    def test_named_product_species(self):
        self.assertTrue(is_named_product_species("Eurasian Jay"))
        self.assertFalse(is_named_product_species("Bird"))
        self.assertFalse(is_named_product_species("Unknown Bird", birder_unknown_label="Unknown Bird"))

    def test_promoteable_deferred_reason(self):
        self.assertTrue(is_frigate_promoteable_reason("accepted_binary_track_classifier_deferred"))
        self.assertTrue(is_frigate_promoteable_reason("review_only_generic_bird"))
        self.assertFalse(is_frigate_promoteable_reason("accepted_species"))

    def test_apply_frigate_named_accept_upgrades_kind(self):
        row = {
            "species_name": "Bird",
            "decision_kind": "review_only_generic",
            "decision_reason": "accepted_binary_track_classifier_deferred",
            "outcome_bucket": "review_only",
            "visit_eligible": True,
            "confidence": 0.2,
        }
        apply_frigate_named_accept(row, species="Great Tit", confidence=0.88)
        self.assertEqual(row["species_name"], "Great Tit")
        self.assertEqual(row["decision_kind"], "accepted_species")
        self.assertEqual(row["decision_reason"], "promoted_by_frigate")
        self.assertEqual(row["outcome_bucket"], "auto_accept")
        self.assertTrue(row["frigate_species_promoted"])

    def test_visit_quality_named_share_and_agreement(self):
        q = compute_visit_quality(
            persisted_rows=[
                {"species_name": "Bird", "decision_kind": "review_only_generic", "outcome_bucket": "review_only"},
                {
                    "species_name": "Great Tit",
                    "decision_kind": "accepted_species",
                    "outcome_bucket": "auto_accept",
                    "decision_reason": "promoted_by_frigate",
                    "frigate_species_promoted": True,
                },
                {
                    "species_name": "Eurasian Jay",
                    "decision_kind": "accepted_species",
                    "outcome_bucket": "auto_accept",
                    "detection_provider": "yolo",
                },
            ],
            mqtt_events=[
                {"source": "frigate", "label": "bird", "sub_label": "Great Tit", "confidence": 0.9},
                {"source": "frigate", "label": "bird", "sub_label": "Eurasian Jay", "confidence": 0.8},
            ],
        )
        self.assertEqual(q["persisted_rows"], 3)
        self.assertEqual(q["named_rows"], 2)
        self.assertEqual(q["named_share"], round(2 / 3, 4))
        self.assertEqual(q["hub_named_rows"], 1)
        self.assertEqual(q["hub_persisted_rows"], 2)
        self.assertEqual(q["named_share_hub"], 0.5)
        self.assertEqual(q["frigate_named_in_window"], 2)
        self.assertEqual(q["frigate_agreement"], 1.0)

    def test_frigate_site_role_authority_and_standalone(self):
        cfg = _Cfg(
            {
                "video": {
                    "cameras": [
                        {
                            "id": "Forest",
                            "tuning_role": "frigate_site",
                            "stream_name": "main",
                            "detect_stream_name": "det",
                        }
                    ]
                },
                "processor.camera_tuning_by_role.frigate_site": {
                    "frigate_species_authority": True,
                    "frigate_standalone_when_no_yolo": True,
                    "frigate_standalone_require_blind_yolo": False,
                },
            }
        )
        self.assertTrue(frigate_species_authority(cfg, camera_id="Forest"))
        self.assertTrue(
            role_detection_flag(cfg, "frigate_standalone_when_no_yolo", camera_id="Forest")
        )
        self.assertFalse(
            role_detection_flag(
                cfg,
                "frigate_standalone_require_blind_yolo",
                camera_id="Forest",
                default=True,
                opt_in=False,
            )
        )

    def test_default_frigate_site_preset_authority_off(self):
        """Hub-first defaults: frigate_site role alone must not enable authority."""
        cfg = _Cfg(
            {
                "video": {
                    "cameras": [
                        {
                            "id": "Forest",
                            "tuning_role": "frigate_site",
                            "stream_name": "main",
                            "detect_stream_name": "det",
                        }
                    ]
                },
                "processor.camera_tuning_by_role.frigate_site": {
                    "frigate_species_authority": False,
                    "frigate_standalone_when_no_yolo": False,
                },
            }
        )
        self.assertFalse(frigate_species_authority(cfg, camera_id="Forest"))

    def test_salvage_flag_not_frigate_sourced_for_hub_row(self):
        hub = {
            "species_name": "Great Tit",
            "decision_kind": "accepted_species",
            "decision_reason": "accepted_classifier",
            "classifier_species_name": "Great Tit",
            "detection_provider": "yolo",
            "frigate_trigger_salvage": True,
        }
        self.assertFalse(is_frigate_sourced_row(hub))
        q = compute_visit_quality(persisted_rows=[hub])
        self.assertEqual(q["hub_named_rows"], 1)
        self.assertEqual(q["named_share_hub"], 1.0)

    def test_review_salvage_reason_not_taxonomy_sourced(self):
        row = {
            "species_name": "Bird",
            "decision_kind": "review_only_generic",
            "decision_reason": "review_only_frigate_trigger_salvage",
            "detection_provider": "yolo",
        }
        self.assertFalse(is_frigate_sourced_row(row))


if __name__ == "__main__":
    unittest.main()
