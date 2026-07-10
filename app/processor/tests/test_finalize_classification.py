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

    appended = enrich_tracks_classifier_at_finalize(tracks, strategy, cfg)

    assert appended == 1
    assert strategy.calls == 1
    event = tracks[7]["classifier_events"][0]
    assert event["species_name"] == "Eurasian Jay"
    assert event["confidence"] == 0.42
    assert event["detector_confidence"] == 0.5
    assert event["combined_confidence"] == 0.21
    assert event["source"] == "finalize_deferred"


def test_enrich_skips_weak_classifier_below_best_guess_floor():
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
            return SimpleNamespace(species_name="Eurasian Jay", top1_confidence=0.05)

    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
            "processor.classifier_finalize_max_tracks": 0,
            "processor.classifier_best_guess_min_confidence": 0.10,
        }
    )

    appended = enrich_tracks_classifier_at_finalize(tracks, _WeakStrategy(), cfg)

    assert appended == 0
    assert "classifier_events" not in tracks[8]


def test_enrich_skips_empty_tracks():
    strategy = _Strategy()
    cfg = _Cfg(
        {
            "processor.pipeline_mode": "linear",
            "processor.classifier_defer_to_finalize": True,
        }
    )
    assert enrich_tracks_classifier_at_finalize({}, strategy, cfg) == 0
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
    appended = enrich_tracks_classifier_at_finalize(tracks, strategy, cfg)
    assert appended == 2
    assert strategy.calls == 2
    assert "classifier_events" in tracks[2]
    assert "classifier_events" in tracks[3]
    assert "classifier_events" not in tracks[1]


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
    appended = enrich_tracks_classifier_at_finalize(tracks, strategy, cfg)
    assert strategy.calls < 20
    assert appended == strategy.calls
