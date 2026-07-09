"""Classifier hints — Frigate, BirdNET, eBird as weighted scoring only (#641)."""

from classifier_hints.collectors import collect_hints
from classifier_hints.scorer import apply_classifier_hints, apply_hints_to_rows

__all__ = [
    "collect_hints",
    "apply_hints_to_rows",
    "apply_classifier_hints",
]
