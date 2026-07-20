"""Tests for linear recording pipeline (detect → classify → reid/behavior → persist)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from decision_maker import DecisionMaker
from linear_pipeline import (
    STAGE_DETECT_TRACK,
    build_linear_decisions,
    evaluate_track_linear,
    frigate_salvage_allow_without_yolo,
    frigate_salvage_opted_in,
    is_linear_pipeline,
    linear_skip_frigate_salvage_paths,
    linear_skip_legacy_fusion_safeguards,
)
from site_adapter import STATUS_ACTIVE, write_site_adapter_manifest


def _bbox_frames(n=3):
    return [
        {"t": i * 0.1, "bbox": [0.1 + i * 0.02, 0.1, 0.3 + i * 0.02, 0.3]}
        for i in range(n)
    ]


def _track(*, conf=0.25, species=None, frames=None, species_conf=0.55):
    clf = []
    if species:
        clf = [
            {
                "species_name": species,
                "confidence": species_conf,
                "combined_confidence": species_conf,
                "detector_confidence": conf,
            }
        ]
    return {
        "start_time": 0.0,
        "end_time": 2.5,
        "detector_events": [{"label": "Bird", "confidence": conf}],
        "classifier_events": clf,
        "frames": frames if frames is not None else _bbox_frames(),
        "best_frame": None,
        "best_frame_score": 0.0,
        "key_frames": [],
    }


class _Cfg:
    def __init__(self, data: dict | None = None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestLinearPipeline(unittest.TestCase):
    def test_is_linear_default_when_unset(self):
        self.assertTrue(is_linear_pipeline(_Cfg({})))
        self.assertTrue(is_linear_pipeline(_Cfg({"processor.pipeline_mode": "linear"})))
        # legacy/dual forced to linear (RC3).
        self.assertTrue(is_linear_pipeline(_Cfg({"processor.pipeline_mode": "legacy"})))
        self.assertTrue(is_linear_pipeline(_Cfg({"processor.pipeline_mode": "dual"})))

    def test_weak_bird_with_bbox_persists(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.min_confidence_binary_bird": 0.08,
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.12),
            min_track_duration=0.5,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])
        self.assertEqual(ev["decision_reason"], "accepted_binary_track_classifier_deferred")
        self.assertEqual(ev["decision_kind"], "review_only_generic")
        self.assertEqual(ev["out_species"], "Bird")
        self.assertEqual(ev["evidence_state"], "detector_only")
        self.assertFalse(ev["visit_eligible"])
        self.assertFalse(ev["notification_eligible"])

    def test_static_frozen_track_deferred_under_binary_track_first(self):
        frozen = [{"t": float(i), "bbox": [0.40, 0.30, 0.48, 0.38]} for i in range(12)]
        cfg = _Cfg(
            {
                "detection.persist_mode": "binary_track_first",
                "processor.pipeline_mode": "linear",
                "processor.linear_static_pinned_reject_enabled": True,
                "processor.track_static_reject_enabled": True,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.25, frames=frozen),
            min_track_duration=0.5,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])
        self.assertEqual(ev["decision_reason"], "accepted_binary_track_classifier_deferred")

    def test_static_frozen_track_rejected_when_legacy_persist(self):
        frozen = [{"t": float(i), "bbox": [0.40, 0.30, 0.48, 0.38]} for i in range(12)]
        cfg = _Cfg(
            {
                "detection.persist_mode": "legacy",
                "processor.pipeline_mode": "linear",
                "processor.linear_static_pinned_reject_enabled": True,
                "processor.track_static_reject_enabled": True,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.25, frames=frozen),
            min_track_duration=0.5,
            min_confidence_to_process=0.12,
        )
        self.assertFalse(ev["accepted"])
        self.assertEqual(ev["decision_reason"], "rejected_static_pinned_track")

    def test_static_reject_can_be_disabled_for_linear(self):
        frozen = [{"t": float(i), "bbox": [0.40, 0.30, 0.48, 0.38]} for i in range(12)]
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.25, frames=frozen),
            min_track_duration=0.5,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])

    def test_no_bbox_rejected(self):
        cfg = _Cfg({"processor.min_confidence_binary_bird": 0.08})
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.5, frames=[]),
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertFalse(ev["accepted"])
        self.assertEqual(ev["decision_reason"], "rejected_no_bbox")

    def test_named_species_from_classifier(self):
        cfg = _Cfg(
            {
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.4, species="Eurasian Jay"),
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])
        self.assertEqual(ev["out_species"], "Eurasian Jay")
        self.assertEqual(ev["decision_reason"], "accepted_species")
        self.assertEqual(ev["decision_kind"], "accepted_species")

    def test_uncertain_named_is_review_only_not_hub_accept(self):
        """best-guess band: named label must not be auto_accept / taxonomy win."""
        cfg = _Cfg(
            {
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.4, species="Eurasian Jay", species_conf=0.12),
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])
        self.assertEqual(ev["out_species"], "Eurasian Jay")
        self.assertEqual(ev["decision_reason"], "accepted_binary_track_classifier_uncertain")
        self.assertEqual(ev["decision_kind"], "review_only_uncertain_species")
        self.assertFalse(ev["visit_eligible"])
        self.assertFalse(ev["notification_eligible"])
        self.assertTrue(ev["classifier_needs_review"])
        from decision_outcome import compute_outcome_bucket
        from recognition_outcome import from_persist_row

        bucket = compute_outcome_bucket(
            accepted=True,
            visit_eligible=ev["visit_eligible"],
            decision_kind=ev["decision_kind"],
        )
        self.assertEqual(bucket, "review_only")
        outcome = from_persist_row(
            {
                "species_name": ev["out_species"],
                "decision_kind": ev["decision_kind"],
                "decision_reason": ev["decision_reason"],
                "classifier_needs_review": True,
                "outcome_bucket": bucket,
                "detection_provider": "yolo",
            }
        )
        self.assertFalse(outcome.hub_taxonomy_win)

    def test_deferred_classify_sets_skip_reason(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.min_confidence_binary_bird": 0.08,
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.2),
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertEqual(ev["decision_kind"], "review_only_generic")
        self.assertEqual(ev["classify_skip_reason"], "deferred")

    def test_budget_skip_reason_copied_from_track(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        track = _track(conf=0.2)
        track["classify_skip_reason"] = "budget"
        ev = evaluate_track_linear(
            app_config=cfg,
            track=track,
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertEqual(ev["classify_skip_reason"], "budget")

    def test_unknown_only_classifier_events_abstain(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.birder_eu_unknown_label": "Unknown Bird",
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        track = _track(conf=0.3)
        track["classifier_events"] = [
            {"species_name": "Unknown Bird", "confidence": 0.9, "combined_confidence": 0.27},
        ]
        ev = evaluate_track_linear(
            app_config=cfg,
            track=track,
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertEqual(ev["out_species"], "Bird")
        self.assertEqual(ev["decision_kind"], "review_only_generic")
        self.assertEqual(ev["classify_skip_reason"], "unknown_abstain")
        self.assertEqual(ev["pipeline_stage"], "classify_enrich")

    def test_build_linear_decisions_via_decision_maker(self):
        dm = DecisionMaker(min_track_duration=0.5, min_confidence_to_process=0.12)
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.min_confidence_binary_bird": 0.08,
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        tracks = {7: _track(conf=0.15)}
        rows = build_linear_decisions(dm, tracks, cfg)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["accepted"])
        self.assertEqual(rows[0]["pipeline_stage"], STAGE_DETECT_TRACK)

    def test_build_linear_decisions_accepts_spatial_split_track_id(self):
        dm = DecisionMaker(min_track_duration=0.5, min_confidence_to_process=0.12)
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.min_confidence_binary_bird": 0.08,
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
                "processor.linear_static_pinned_reject_enabled": False,
            }
        )
        tracks = {"1:s1": _track(conf=0.15)}
        rows = build_linear_decisions(dm, tracks, cfg)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["track_id"], "1:s1")
        self.assertTrue(rows[0]["accepted"])

    def test_get_decisions_routes_linear(self):
        dm = DecisionMaker(min_track_duration=0.0, min_confidence_to_process=0.12)
        mock_cfg = MagicMock()
        mock_cfg.get.side_effect = lambda k, d=None: {
            "processor.pipeline_mode": "linear",
            "processor.min_confidence_binary_bird": 0.08,
            "processor.classifier_best_guess_min_confidence": 0.10,
            "processor.birder_eu_min_confidence": 0.15,
            "processor.linear_static_pinned_reject_enabled": False,
        }.get(k, d)

        with unittest.mock.patch("app_config.app_config.app_config", mock_cfg):
            rows = dm.get_decisions({1: _track(conf=0.2)})
        self.assertTrue(rows[0]["accepted"])

    def test_linear_skip_legacy_fusion_safeguards_only_in_linear(self):
        linear = _Cfg({"processor.pipeline_mode": "linear"})
        legacy = _Cfg({"processor.pipeline_mode": "legacy"})
        dual = _Cfg({"processor.pipeline_mode": "dual"})
        self.assertTrue(linear_skip_legacy_fusion_safeguards(linear))
        self.assertTrue(linear_skip_legacy_fusion_safeguards(legacy))  # forced linear
        self.assertTrue(linear_skip_legacy_fusion_safeguards(dual))  # RC3: dual→linear

    def test_linear_skips_salvage_persist_bypass(self):
        linear = _Cfg({"processor.pipeline_mode": "linear"})
        dual = _Cfg({"processor.pipeline_mode": "dual"})
        self.assertTrue(linear_skip_legacy_fusion_safeguards(linear))
        self.assertTrue(linear_skip_legacy_fusion_safeguards(dual))

    def test_linear_skips_frigate_salvage_by_default(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "video": {"cameras": [{"id": "Forest", "tuning_role": "feeder_far", "stream_name": "main", "detect_stream_name": "det"}]},
                "processor.camera_tuning_by_role.feeder_far": {},
            }
        )
        self.assertTrue(linear_skip_frigate_salvage_paths(cfg, camera_id="Forest"))

    def test_frigate_site_role_opts_in_salvage_on_linear(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "video": {"cameras": [{"id": "Forest", "tuning_role": "frigate_site", "stream_name": "main", "detect_stream_name": "det"}]},
                "processor.camera_tuning_by_role.frigate_site": {
                    "frigate_trigger_review_salvage_enabled": True,
                },
            }
        )
        self.assertTrue(frigate_salvage_opted_in(cfg, camera_id="Forest"))
        self.assertTrue(frigate_salvage_opted_in(cfg, camera_id="main"))
        self.assertFalse(linear_skip_frigate_salvage_paths(cfg, camera_id="main"))

    def test_global_frigate_salvage_opt_in(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "detection.frigate_trigger_review_salvage_enabled": True,
            }
        )
        self.assertTrue(frigate_salvage_opted_in(cfg))
        self.assertFalse(linear_skip_frigate_salvage_paths(cfg))

    def test_role_allow_without_yolo_override(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "video": {"cameras": [{"id": "Forest", "tuning_role": "frigate_site", "stream_name": "main", "detect_stream_name": "det"}]},
                "processor.camera_tuning_by_role.frigate_site": {
                    "frigate_trigger_review_salvage_allow_without_yolo_tracks": True,
                },
            }
        )
        self.assertTrue(frigate_salvage_allow_without_yolo(cfg, camera_id="main"))

    def test_site_prior_rerank_picks_prior_species(self):
        """Soft lower-conf prior species beats higher-conf rival after prior delta."""
        with tempfile.TemporaryDirectory() as tmp:
            write_site_adapter_manifest(
                tmp,
                version="unit-prior-rerank",
                source="unit_test",
                status=STATUS_ACTIVE,
                canary_share=1.0,
                species_priors={"house sparrow": 0.20},
            )
            cfg = _Cfg(
                {
                    "processor.classifier_best_guess_min_confidence": 0.10,
                    "processor.birder_eu_min_confidence": 0.15,
                    "processor.linear_static_pinned_reject_enabled": False,
                }
            )
            track = _track(conf=0.4, species=None)
            track["track_id"] = 42
            track["classifier_events"] = [
                {
                    "species_name": "Eurasian Jay",
                    "confidence": 0.12,
                    "combined_confidence": 0.12,
                },
                {
                    "species_name": "House Sparrow",
                    "confidence": 0.08,
                    "combined_confidence": 0.08,
                    "soft": True,
                },
            ]
            with patch("processor_support.get_data_dir", return_value=tmp):
                ev = evaluate_track_linear(
                    app_config=cfg,
                    track=track,
                    min_track_duration=0.0,
                    min_confidence_to_process=0.12,
                )
            self.assertTrue(ev["accepted"])
            self.assertEqual(ev["out_species"], "House Sparrow")
            meta = (ev.get("classifier_candidate") or {})
            # prior: 0.08+0.20=0.28 > jay 0.12
            self.assertGreaterEqual(
                float(meta.get("avg_classifier_confidence") or 0.0), 0.25
            )

    def test_prior_rerank_does_not_invent_over_strong_pigeon(self):
        """Tiny dove soft must not beat strong pigeon after prior (no confuse override)."""
        with tempfile.TemporaryDirectory() as tmp:
            write_site_adapter_manifest(
                tmp,
                version="unit-columbidae",
                source="unit_test",
                status=STATUS_ACTIVE,
                canary_share=1.0,
                species_priors={
                    "eurasian collared-dove": 0.35,
                    "common wood pigeon": 0.02,
                },
            )
            cfg = _Cfg(
                {
                    "processor.classifier_best_guess_min_confidence": 0.10,
                    "processor.birder_eu_min_confidence": 0.15,
                    "processor.linear_static_pinned_reject_enabled": False,
                }
            )
            track = _track(conf=0.4, species=None)
            track["track_id"] = 7
            track["classifier_events"] = [
                {
                    "species_name": "Common Wood Pigeon",
                    "confidence": 0.78,
                    "combined_confidence": 0.78,
                },
                {
                    "species_name": "Eurasian Collared-Dove",
                    "confidence": 0.04,
                    "combined_confidence": 0.04,
                    "soft": True,
                    "soft_reason": "topk_prior",
                },
            ]
            with patch("processor_support.get_data_dir", return_value=tmp):
                ev = evaluate_track_linear(
                    app_config=cfg,
                    track=track,
                    min_track_duration=0.0,
                    min_confidence_to_process=0.12,
                )
            self.assertTrue(ev["accepted"])
            self.assertEqual(ev["out_species"], "Common Wood Pigeon")

    def test_prior_rerank_dove_wins_mid_conf_pigeon(self):
        """Real dove near-miss + prior beats mid-conf pigeon."""
        with tempfile.TemporaryDirectory() as tmp:
            write_site_adapter_manifest(
                tmp,
                version="unit-dove-mid",
                source="unit_test",
                status=STATUS_ACTIVE,
                canary_share=1.0,
                species_priors={
                    "eurasian collared dove": 0.20,
                    "common wood pigeon": 0.02,
                },
            )
            cfg = _Cfg(
                {
                    "processor.classifier_best_guess_min_confidence": 0.10,
                    "processor.birder_eu_min_confidence": 0.15,
                    "processor.linear_static_pinned_reject_enabled": False,
                }
            )
            track = _track(conf=0.4, species=None)
            track["track_id"] = 8
            track["classifier_events"] = [
                {
                    "species_name": "Common Wood Pigeon",
                    "confidence": 0.28,
                    "combined_confidence": 0.28,
                },
                {
                    "species_name": "Eurasian collared dove",
                    "confidence": 0.18,
                    "combined_confidence": 0.18,
                    "soft": True,
                },
            ]
            with patch("processor_support.get_data_dir", return_value=tmp):
                ev = evaluate_track_linear(
                    app_config=cfg,
                    track=track,
                    min_track_duration=0.0,
                    min_confidence_to_process=0.12,
                )
            self.assertTrue(ev["accepted"])
            self.assertEqual(ev["out_species"], "Eurasian collared dove")


if __name__ == "__main__":
    unittest.main()
