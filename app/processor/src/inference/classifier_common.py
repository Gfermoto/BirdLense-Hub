"""Shared classifier helpers (birder_eu and detector stack)."""

from __future__ import annotations

import numpy as np

UNKNOWN_BIRD_LABEL = "Unknown Bird"
SQUIRREL_SPECIES_LABEL = "Rodent"


def entropy_margin(probs: np.ndarray) -> tuple[float, float]:
    arr = np.asarray(probs, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return 0.0, 0.0
    p = np.clip(arr, 1e-12, 1.0)
    s = float(p.sum())
    if s <= 0:
        return 0.0, 0.0
    p = p / s
    ent = float(-np.sum(p * np.log(p)))
    if p.size < 2:
        return ent, float(p[0])
    top2 = np.partition(p, -2)[-2:]
    margin = float(np.max(top2) - np.min(top2))
    return ent, margin


def normalize_species_label(name: str) -> str:
    # Collapse hyphen/underscore variants so "Collared-Dove" matches Birder "collared dove".
    raw = str(name or "").replace("_OR_", "/").replace("_", " ").replace("-", " ")
    return " ".join(raw.split()).strip()
