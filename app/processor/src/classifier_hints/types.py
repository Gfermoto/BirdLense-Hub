"""Typed hint payloads for classifier scoring (ADR #634, #641)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HintSource(str, Enum):
    BIRDNET = "birdnet"
    EBIRD_REGIONAL = "ebird_regional"
    FRIGATE_LABEL = "frigate_label"
    MULTICAM_PEER = "multicam_peer"


@dataclass(frozen=True)
class HintPayload:
    source: HintSource
    species: str
    weight: float
    score: float
    raw_confidence: float = 0.0
    support_count: int = 1
    meta: dict = field(default_factory=dict)


@dataclass
class HintTraceEntry:
    source: str
    species: str
    delta: float
    weight: float
    score: float
