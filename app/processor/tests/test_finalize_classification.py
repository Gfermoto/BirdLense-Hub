"""Tests for deferred classifier enrichment at recording finalization."""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from finalize_classification import enrich_tracks_classifier_at_finalize  # noqa: E402


class _Cfg:
    def __init__(self, data: dict | None = None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)


class _Strategy:
    def __init__(self):
        self.calls = 0

    def _classify_crop(self, _crop):
        self.calls += 1
        return SimpleNamespace(
            species_name="Eurasian Jay",
            top1_confidence=0.42,
            entropy=1.2,
            top1_top2_margin=0.11,
        )


def test_enrich_tracks_classifier_at_finalize_uses_top1_confidence():
    tracks = {
        7: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "end_time": 3.5,
        }
    }
    strategy = _Strategy()
    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_key_frames": 1,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
        }
    )

    outcome = enrich_tracks_classifier_at_finalize(tracks, strategy, cfg)

    assert outcome["appended"] == 1
    assert outcome["eligible"] == 1
    assert outcome["no_crop"] == 0
    assert strategy.calls == 1
    event = tracks[7]["classifier_events"][0]
    assert event["species_name"] == "Eurasian Jay"
    assert event["confidence"] == 0.42
    assert event["detector_confidence"] == 0.5
    assert event["combined_confidence"] == 0.21
    assert event["source"] == "finalize_deferred"


def test_enrich_skips_weak_classifier_below_soft_floor():
    tracks = {
        8: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "end_time": 3.5,
        }
    }

    class _WeakStrategy:
        def _classify_crop(self, _crop):
            return SimpleNamespace(species_name="Eurasian Jay", top1_confidence=0.02)

    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
            "processor.classifier_soft_min_confidence": 0.04,
        }
    )

    outcome = enrich_tracks_classifier_at_finalize(tracks, _WeakStrategy(), cfg)

    assert outcome["appended"] == 0
    assert outcome["low_conf"] >= 1
    assert "classifier_events" not in tracks[8]


def test_enrich_keeps_soft_near_miss_below_min_guess():
    tracks = {
        9: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "end_time": 3.5,
        }
    }

    class _NearMissStrategy:
        def _classify_crop(self, _crop):
            return SimpleNamespace(
                species_name="House Sparrow",
                top1_confidence=0.05,
                entropy=2.0,
                top1_top2_margin=0.02,
            )

    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
            "processor.classifier_soft_events_enabled": True,
            "processor.classifier_soft_min_confidence": 0.04,
        }
    )

    outcome = enrich_tracks_classifier_at_finalize(tracks, _NearMissStrategy(), cfg)

    assert outcome["appended"] == 1
    ev = tracks[9]["classifier_events"][0]
    assert ev["species_name"] == "House Sparrow"
    assert ev["soft"] is True
    assert ev["soft_reason"] == "below_min_guess"


def test_enrich_soft_alt_argmax_from_unknown():
    tracks = {
        10: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "end_time": 3.5,
        }
    }

    class _UnknownAltStrategy:
        def _classify_crop(self, _crop):
            return SimpleNamespace(
                species_name="Unknown Bird",
                top1_confidence=0.40,
                entropy=2.5,
                top1_top2_margin=0.01,
                alt_species_name="Fieldfare",
                alt_confidence=0.08,
            )

    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
            "processor.classifier_soft_events_enabled": True,
            "processor.classifier_soft_min_confidence": 0.04,
        }
    )

    outcome = enrich_tracks_classifier_at_finalize(tracks, _UnknownAltStrategy(), cfg)

    assert outcome["appended"] == 1
    ev = tracks[10]["classifier_events"][0]
    assert ev["species_name"] == "Fieldfare"
    assert ev["confidence"] == 0.08
    assert ev["soft"] is True
    assert ev["soft_reason"] == "unknown_alt_argmax"


def test_enrich_runner_up_soft_when_prior_applies(tmp_path, monkeypatch):
    from site_adapter import STATUS_ACTIVE, write_site_adapter_manifest

    write_site_adapter_manifest(
        tmp_path,
        version="ru-prior",
        source="unit_test",
        status=STATUS_ACTIVE,
        canary_share=1.0,
        species_priors={"eurasian collared-dove": 0.25},
    )
    monkeypatch.setattr("processor_support.get_data_dir", lambda: str(tmp_path))

    tracks = {
        11: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "end_time": 3.5,
            "track_id": 11,
        }
    }

    class _PigeonTopStrategy:
        def _classify_crop(self, _crop):
            return SimpleNamespace(
                species_name="Common Wood Pigeon",
                top1_confidence=0.42,
                entropy=1.5,
                top1_top2_margin=0.05,
                runner_up_species_name="Eurasian Collared-Dove",
                runner_up_confidence=0.12,
                top_named=[
                    ("Common Wood Pigeon", 0.42),
                    ("Eurasian Collared-Dove", 0.12),
                    ("Great Tit", 0.08),
                ],
            )

    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
            "processor.classifier_soft_events_enabled": True,
            "processor.classifier_soft_min_confidence": 0.01,
        }
    )

    outcome = enrich_tracks_classifier_at_finalize(tracks, _PigeonTopStrategy(), cfg)
    assert outcome["appended"] >= 2
    names = [e["species_name"] for e in tracks[11]["classifier_events"]]
    assert "Common Wood Pigeon" in names
    assert "Eurasian Collared-Dove" in names
    soft = [e for e in tracks[11]["classifier_events"] if e.get("soft")]
    assert soft and soft[0]["soft_reason"] == "topk_prior"



def test_enrich_dove_soft_under_hard_pigeon(tmp_path, monkeypatch):
    """High-margin pigeon still soft-appends #2 dove when site prior applies."""
    from types import SimpleNamespace
    from finalize_classification import enrich_tracks_classifier_at_finalize
    from site_adapter import write_site_adapter_manifest

    write_site_adapter_manifest(
        tmp_path,
        version="t",
        source="test",
        status="canary",
        canary_share=1.0,
        species_priors={"eurasian collared dove": 0.12, "common wood pigeon": 0.02},
    )
    monkeypatch.setattr(
        "processor_support.get_data_dir", lambda: tmp_path, raising=False
    )
    monkeypatch.setattr(
        "site_adapter.get_data_dir", lambda: tmp_path, raising=False
    )
    # finalize imports get_data_dir inside fn — patch module used by finalize
    import processor_support as ps
    monkeypatch.setattr(ps, "get_data_dir", lambda: tmp_path)

    tracks = {
        7: {
            "detector_events": [{"label": "Bird", "confidence": 0.9}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "end_time": 1.0,
            "track_id": 7,
        }
    }

    class _HardPigeon:
        def _classify_crop(self, _crop):
            return SimpleNamespace(
                species_name="Common wood pigeon",
                confidence=0.85,
                top1_confidence=0.85,
                entropy=0.4,
                top1_top2_margin=0.85,
                runner_up_species_name="Eurasian collared dove",
                runner_up_confidence=0.0037,
                top_named=[
                    ("Common wood pigeon", 0.8529),
                    ("Eurasian collared dove", 0.0037),
                    ("European greenfinch", 0.0002),
                ],
            )

    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
            "processor.classifier_soft_events_enabled": True,
            "processor.classifier_soft_min_confidence": 0.01,
        }
    )
    outcome = enrich_tracks_classifier_at_finalize(tracks, _HardPigeon(), cfg)
    names = [e["species_name"] for e in tracks[7]["classifier_events"]]
    assert "Common wood pigeon" in names or "Common Wood Pigeon" in names
    assert any("collared" in n.lower() and "dove" in n.lower() for n in names)
    soft = [e for e in tracks[7]["classifier_events"] if e.get("soft")]
    assert soft and soft[0]["soft_reason"] == "topk_prior"
    assert outcome["appended"] >= 2


def test_enrich_skips_empty_tracks():
    strategy = _Strategy()
    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
        }
    )
    outcome = enrich_tracks_classifier_at_finalize({}, strategy, cfg)
    assert outcome["appended"] == 0
    assert outcome["skip_reason"] == "no_tracks"
    assert strategy.calls == 0


def test_enrich_respects_max_tracks_top_score():
    tracks = {
        1: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 1.0,
            "end_time": 1.0,
        },
        2: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 9.0,
            "end_time": 1.0,
        },
        3: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 5.0,
            "end_time": 1.0,
        },
    }
    strategy = _Strategy()
    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 2,
            "processor.classifier_best_guess_min_confidence": 0.10,
        }
    )
    outcome = enrich_tracks_classifier_at_finalize(tracks, strategy, cfg)
    assert outcome["appended"] == 2
    assert outcome["skipped_budget"] == 1
    assert strategy.calls == 2
    assert "classifier_events" in tracks[2]
    assert "classifier_events" in tracks[3]
    assert "classifier_events" not in tracks[1]


def test_enrich_skips_unknown_and_tries_next_crop():
    tracks = {
        9: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "key_frames": [{"crop": object(), "score": 3.0}],
            "end_time": 3.5,
        }
    }

    class _MixedStrategy:
        def __init__(self):
            self.calls = 0

        def _classify_crop(self, _crop):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    species_name="Unknown Bird",
                    top1_confidence=0.9,
                    entropy=0.5,
                    top1_top2_margin=0.8,
                )
            return SimpleNamespace(
                species_name="Great Tit",
                top1_confidence=0.35,
                entropy=1.1,
                top1_top2_margin=0.12,
            )

    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_key_frames": 3,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
        }
    )
    strategy = _MixedStrategy()
    outcome = enrich_tracks_classifier_at_finalize(tracks, strategy, cfg)
    assert outcome["appended"] == 1
    assert outcome["unknown"] >= 1
    assert strategy.calls >= 2
    assert tracks[9]["classifier_events"][0]["species_name"] == "Great Tit"


def test_enrich_respects_max_runtime_budget():
    """Wall-clock cap must stop before classifying every track."""
    tracks = {
        i: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 2.0,
            "end_time": 1.0,
        }
        for i in range(20)
    }

    class _SlowStrategy:
        def __init__(self):
            self.calls = 0

        def _classify_crop(self, _crop):
            self.calls += 1
            time.sleep(0.05)
            return SimpleNamespace(
                species_name="Eurasian Jay",
                top1_confidence=0.5,
                entropy=1.0,
                top1_top2_margin=0.2,
            )

    strategy = _SlowStrategy()
    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_finalize_max_runtime_ms": 80,
            "processor.classifier_best_guess_min_confidence": 0.10,
        }
    )
    outcome = enrich_tracks_classifier_at_finalize(tracks, strategy, cfg)
    assert strategy.calls < 20
    assert outcome["appended"] == strategy.calls
    assert outcome["timed_out"] is True


def test_enrich_track_ids_filter_and_overrides():
    tracks = {
        1: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 3.0,
            "end_time": 1.0,
        },
        2: {
            "detector_events": [{"label": "Bird", "confidence": 0.5}],
            "best_frame": object(),
            "best_frame_score": 1.0,
            "end_time": 2.0,
        },
    }
    strategy = _Strategy()
    cfg = _Cfg(
        {
            "processor.classifier_defer_to_finalize": False,
            "processor.classifier_finalize_max_key_frames": 1,
            "processor.classifier_finalize_max_tracks": 1,
            "processor.classifier_best_guess_min_confidence": 0.10,
        }
    )
    outcome = enrich_tracks_classifier_at_finalize(
        tracks,
        strategy,
        cfg,
        track_ids={2},
        max_tracks=5,
        max_runtime_ms=5000,
        event_source="async_classify_patch",
        require_defer_enabled=False,
    )
    assert outcome["appended"] == 1
    assert outcome["eligible"] == 1
    assert "classifier_events" not in tracks[1]
    assert tracks[2]["classifier_events"][0]["source"] == "async_classify_patch"

