"""Unified species vocabulary: classifier + arbitration (#506)."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def vocab_env(tmp_path):
    processor = tmp_path / "processor"
    bundle = processor / "models" / "classification" / "convnext_v2_tiny_eu-common256px"
    bundle.mkdir(parents=True)
    (bundle / "class_labels.txt").write_text(
        "Pica pica (Eurasian Magpie)\nCyanolyca mirabilis (Azure Jay)\n",
        encoding="utf-8",
    )

    def getter(key, default=None):
        cfg = {
            "processor.classifier_engine": "birder_eu",
            "processor.birder_eu_variant": "convnext_v2_tiny_eu-common256px",
            "processor.models.classifier": str(bundle.relative_to(processor)) + "/convnext_v2_tiny_eu-common256px.onnx",
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
            assert snap.allows_ingest_name("Pica pica (Eurasian Magpie)")
            assert snap.allows_ingest_name("Eurasian Magpie")
