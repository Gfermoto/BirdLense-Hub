"""Trapper: native class names and open detector scope."""

from detector_labels import (
    normalize_detector_label,
    resolve_detector_scope_set,
)


def test_native_label_preserves_squirrel_not_rodent():
    assert normalize_detector_label("Eurasian Red Squirrel", native=True) == "Eurasian Red Squirrel"
    assert normalize_detector_label("Eurasian Red Squirrel", native=False) == "Rodent"


def test_native_label_preserves_cat():
    assert normalize_detector_label("Cat", native=True) == "Cat"
    assert normalize_detector_label("Cat", native=False) == "Rodent"


def test_empty_scope_means_all_classes():
    cfg = {"processor.detector_native_class_labels": True}
    assert resolve_detector_scope_set([], cfg) is None
    assert resolve_detector_scope_set(None, cfg) is None


def test_scope_whitelist_native():
    cfg = {"processor.detector_native_class_labels": True}
    scope = resolve_detector_scope_set(["Bird", "Red Fox"], cfg)
    assert scope == {"Bird", "Red Fox"}
