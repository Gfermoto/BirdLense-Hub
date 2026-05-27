"""Unified species vocabulary: classifier + arbitration (#506)."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def vocab_env(tmp_path):
    processor = tmp_path / "processor"
    weights = processor / "models" / "classification" / "weights" / "birds_classifier_efficientnetb2"
    weights.mkdir(parents=True)
    import json

    (weights / "config.json").write_text(
        json.dumps({"id2label": {"0": "EURASIAN MAGPIE", "1": "AZURE JAY"}}),
        encoding="utf-8",
    )

    def getter(key, default=None):
        cfg = {
            "processor.classifier_engine": "efficientnet_b2",
            "processor.models.classifier_efficientnet_b2": str(weights.relative_to(processor)),
            "species.catalog_allowlist_extra": ["Rodent"],
            "species.catalog_strict_ingest": True,
            "detection.species_mapping": {
                "Garrulus glandarius (Eurasian Jay)": "Eurasian Jay",
            },
            "ebird.species_mapping": {},
        }
        return cfg.get(key, default)

    return getter, processor


def test_vocabulary_allows_arbitration_not_in_classifier(vocab_env):
    getter, processor = vocab_env
    with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
        with patch("services.species_catalog.vocabulary.app_config") as mock_cfg:
            mock_cfg.get = getter
            from services.species_catalog.vocabulary import (
                clear_species_vocabulary_cache,
                get_species_vocabulary_snapshot,
            )

            clear_species_vocabulary_cache()
            snap = get_species_vocabulary_snapshot()
            assert snap.allows_ingest_name("Eurasian Jay")
            assert not snap.allows_ingest_name("Totally Made Up Bird XYZ")


def test_vocabulary_classifier_canonical_keys(vocab_env):
    getter, processor = vocab_env
    with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
        with patch("services.species_catalog.vocabulary.app_config") as mock_cfg:
            mock_cfg.get = getter
            from services.species_catalog.vocabulary import (
                clear_species_vocabulary_cache,
                get_species_vocabulary_snapshot,
            )

            clear_species_vocabulary_cache()
            snap = get_species_vocabulary_snapshot()
            assert snap.allows_ingest_name("EURASIAN MAGPIE")
            assert snap.allows_ingest_name("Eurasian Magpie")
