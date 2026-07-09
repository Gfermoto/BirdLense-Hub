"""Allowlist привязан к активному классификатору, без auto-merge legacy YOLO (#506)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

_BIRDER_LABELS = (
    Path(__file__).resolve().parents[2]
    / "processor"
    / "models"
    / "classification"
    / "convnext_v2_tiny_eu-common256px"
    / "class_labels.txt"
)


@pytest.fixture
def birder_fixture(tmp_path):
    processor = tmp_path / "processor"
    bundle = processor / "models" / "classification" / "convnext_v2_tiny_eu-common256px"
    bundle.mkdir(parents=True)
    (bundle / "class_labels.txt").write_text(
        "Pica pica (Eurasian Magpie)\nGarrulus glandarius (Eurasian Jay)\nRodent\n",
        encoding="utf-8",
    )
    yolo_names = processor / "models" / "classification" / "weights" / "class_names.txt"
    yolo_names.parent.mkdir(parents=True, exist_ok=True)
    yolo_names.write_text("Parus major (Great Tit)\n", encoding="utf-8")

    def getter(key, default=None):
        cfg = {
            "species.catalog_allowlist_follow_classifier_engine": True,
            "species.catalog_allowlist_use_active_classifier": True,
            "species.catalog_allowlist_file": "models/classification/weights/class_names.txt",
            "species.catalog_allowlist_extra": ["Rodent"],
            "processor.classifier_engine": "birder_eu",
            "processor.birder_eu_variant": "convnext_v2_tiny_eu-common256px",
            "processor.models.classifier": str(bundle.relative_to(processor)) + "/convnext_v2_tiny_eu-common256px.onnx",
        }
        return cfg.get(key, default)

    return getter, processor


def test_allowlist_uses_classifier_id2label_not_yolo_file(birder_fixture):
    getter, processor = birder_fixture
    with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
        from services.species_catalog.allowlist import (
            clear_allowlist_cache,
            load_active_classifier_label_names,
            load_catalog_allowlist_norm_keys,
            species_matches_allowlist,
        )

        clear_allowlist_cache()
        labels = load_active_classifier_label_names(getter)
        assert labels is not None
        assert "Pica pica (Eurasian Magpie)" in labels
        assert "Garrulus glandarius (Eurasian Jay)" in labels
        keys = load_catalog_allowlist_norm_keys(getter)
        assert keys is not None
        assert species_matches_allowlist("Eurasian Magpie", keys)
        assert species_matches_allowlist("Eurasian Jay", keys)
        # EU-only YOLO line not merged unless in id2label
        assert not species_matches_allowlist("Great Tit", keys)


@pytest.fixture
def birder_eu_fixture(tmp_path):
    processor = tmp_path / "processor"
    weights = processor / "models" / "classification" / "convnext_v2_tiny_eu-common256px"
    weights.mkdir(parents=True)
    (weights / "class_labels.txt").write_text(
        "eurasian magpie\neurasian jay\n",
        encoding="utf-8",
    )

    def getter(key, default=None):
        cfg = {
            "species.catalog_allowlist_follow_classifier_engine": True,
            "species.catalog_allowlist_use_active_classifier": True,
            "species.catalog_allowlist_extra": ["Rodent"],
            "processor.classifier_engine": "birder_eu",
            "processor.models.classifier_birder_eu": str(
                weights.relative_to(processor),
            ),
        }
        return cfg.get(key, default)

    return getter, processor


def test_birder_allowlist_title_case_labels_match_db_names(birder_eu_fixture):
    getter, processor = birder_eu_fixture
    with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
        from services.species_catalog.allowlist import (
            clear_allowlist_cache,
            load_catalog_allowlist_norm_keys,
            species_matches_allowlist,
        )

        clear_allowlist_cache()
        keys = load_catalog_allowlist_norm_keys(getter)
        assert keys is not None
        assert species_matches_allowlist("Eurasian Magpie", keys)
        assert species_matches_allowlist("Eurasian Jay", keys)
        assert species_matches_allowlist("eurasian jay", keys)


def test_birder_allowlist_total_is_labels_plus_rodent(birder_eu_fixture):
    getter, processor = birder_eu_fixture
    with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
        from services.species_catalog.allowlist import (
            clear_allowlist_cache,
            load_catalog_allowlist_names,
        )

        clear_allowlist_cache()
        names = load_catalog_allowlist_names(getter)
        assert names is not None
        assert len(names) == 3
        assert "Rodent" in names


@pytest.mark.skipif(not _BIRDER_LABELS.is_file(), reason="Birder class_labels.txt not in tree")
def test_birder_repo_allowlist_has_707_bird_classes():
    lines = [ln for ln in _BIRDER_LABELS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 707


def test_scientific_name_from_canonical_mapping():
    from services.species_catalog.allowlist import scientific_name_from_canonical_mapping

    mapping = {"Garrulus glandarius (Eurasian Jay)": "Eurasian Jay"}
    assert scientific_name_from_canonical_mapping("Eurasian Jay", mapping) == "Garrulus glandarius"


def test_allowlist_total_matches_classifier_plus_extras(birder_fixture):
    getter, processor = birder_fixture
    with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
        from services.species_catalog.allowlist import (
            clear_allowlist_cache,
            load_catalog_allowlist_names,
        )

        clear_allowlist_cache()
        names = load_catalog_allowlist_names(getter)
        assert names is not None
        assert len(names) == 3
