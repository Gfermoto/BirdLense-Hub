"""Allowlist: engine class_labels + configured class_names (EU) merge (#506)."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def app_config_get_follow_engine(tmp_path):
  processor = tmp_path / "processor"
  weights = processor / "models" / "classification" / "weights"
  eff = weights / "birds_classifier_efficientnetb2"
  eff.mkdir(parents=True)
  (eff / "class_labels.txt").write_text("EURASIAN MAGPIE\nRODENT\n", encoding="utf-8")
  (weights / "class_names.txt").write_text(
      "Garrulus glandarius (Eurasian Jay)\nParus major (Great Tit)\n",
      encoding="utf-8",
  )

  def getter(key, default=None):
    cfg = {
      "species.catalog_allowlist_follow_classifier_engine": True,
      "species.catalog_allowlist_file": "models/classification/weights/class_names.txt",
      "species.catalog_allowlist_extra": ["Rodent"],
      "processor.classifier_engine": "efficientnet_b2",
      "processor.models.classifier_efficientnet_b2": str(eff.relative_to(processor)),
    }
    return cfg.get(key, default)

  return getter, processor


def test_allowlist_merges_engine_and_configured_class_names(app_config_get_follow_engine):
  getter, processor = app_config_get_follow_engine
  with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
    from services.species_catalog.allowlist import (
      clear_allowlist_cache,
      load_catalog_allowlist_norm_keys,
      resolve_all_allowlist_paths,
      species_matches_allowlist,
    )

    clear_allowlist_cache()
    paths = resolve_all_allowlist_paths(getter)
    assert len(paths) == 2
    keys = load_catalog_allowlist_norm_keys(getter)
    assert keys is not None
    assert "eurasian jay" in keys
    assert "eurasian magpie" in keys
    assert species_matches_allowlist("Eurasian Jay", keys)


def test_allowlist_scientific_lookup_after_merge(app_config_get_follow_engine):
  getter, processor = app_config_get_follow_engine
  with patch("services.species_catalog.allowlist._processor_root", return_value=str(processor)):
    from services.species_catalog.allowlist import (
      allowlist_scientific_name_for_display_name,
      clear_allowlist_cache,
    )

    clear_allowlist_cache()
    sci = allowlist_scientific_name_for_display_name("Eurasian Jay", getter)
    assert sci == "Garrulus glandarius"
