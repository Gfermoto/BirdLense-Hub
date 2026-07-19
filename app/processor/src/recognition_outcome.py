"""Typed recognition product outcome (RC1).

Presence recording and species taxonomy are different products. Persist rows
still carry legacy ``decision_kind`` / ``decision_reason``; this module is the
single derivation surface until callers migrate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from visit_contract import is_frigate_sourced_row, is_named_product_species


class OutcomeKind(str, Enum):
    """Product-level outcome. Not a detector reliability flag."""

    PRESENCE = "presence"
    REVIEW = "review"
    NAMED_ACCEPT = "named_accept"
    NAMED_REJECT = "named_reject"


@dataclass(frozen=True)
class RecognitionOutcome:
    kind: OutcomeKind
    species_name: str | None
    presence_label: str | None
    authority: str
    skip_reason: str | None = None
    decision_kind: str | None = None
    decision_reason: str | None = None
    hub_taxonomy_win: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


def _species_of(row: Mapping[str, Any]) -> str:
    for key in ("species_name", "accepted_species", "classifier_species_name"):
        raw = row.get(key)
        if raw is None:
            continue
        name = str(raw).strip()
        if name:
            return name
    return ""


def _authority_of(row: Mapping[str, Any]) -> str:
    if is_frigate_sourced_row(row):
        return "frigate"
    reason = str(row.get("decision_reason") or "").strip().lower()
    if "salvage" in reason:
        return "salvage"
    if row.get("classifier_species_name") is not None or "classifier" in reason:
        return "hub_classifier"
    provider = str(row.get("detection_provider") or "").strip().lower()
    if provider in {"yolo", "hub", "onnx"}:
        return "hub_detector"
    if provider:
        return provider
    return "unknown"


def from_persist_row(
    row: Mapping[str, Any] | None,
    *,
    birder_unknown_label: str | None = None,
) -> RecognitionOutcome:
    """Derive ``RecognitionOutcome`` from a persisted / decided track row."""
    if not isinstance(row, Mapping):
        return RecognitionOutcome(
            kind=OutcomeKind.NAMED_REJECT,
            species_name=None,
            presence_label=None,
            authority="unknown",
            skip_reason="missing_row",
        )

    species = _species_of(row)
    kind_raw = str(row.get("decision_kind") or "").strip().lower()
    reason = str(row.get("decision_reason") or "").strip().lower()
    bucket = str(row.get("outcome_bucket") or "").strip().lower()
    skip = row.get("classify_skip_reason") or row.get("skip_reason")
    skip_reason = str(skip).strip() if skip else None
    authority = _authority_of(row)
    named = is_named_product_species(species, birder_unknown_label=birder_unknown_label)
    frigate = is_frigate_sourced_row(row)

    if kind_raw == "rejected" or bucket == "reject":
        return RecognitionOutcome(
            kind=OutcomeKind.NAMED_REJECT,
            species_name=species or None,
            presence_label=None if named else (species or None),
            authority=authority,
            skip_reason=skip_reason,
            decision_kind=kind_raw or None,
            decision_reason=reason or None,
            hub_taxonomy_win=False,
        )

    if kind_raw.startswith("review_only") or bucket == "review_only":
        return RecognitionOutcome(
            kind=OutcomeKind.REVIEW,
            species_name=species if named else None,
            presence_label=None if named else (species or "Bird"),
            authority=authority,
            skip_reason=skip_reason,
            decision_kind=kind_raw or None,
            decision_reason=reason or None,
            hub_taxonomy_win=False,
        )

    if kind_raw in {"accepted_generic", "accepted_binary"} or (
        "fallback" in reason and kind_raw != "accepted_species"
    ):
        return RecognitionOutcome(
            kind=OutcomeKind.PRESENCE,
            species_name=None,
            presence_label=species or "Bird",
            authority=authority,
            skip_reason=skip_reason,
            decision_kind=kind_raw or None,
            decision_reason=reason or None,
            hub_taxonomy_win=False,
        )

    if kind_raw == "accepted_species" or bucket == "auto_accept":
        if named and not frigate:
            return RecognitionOutcome(
                kind=OutcomeKind.NAMED_ACCEPT,
                species_name=species,
                presence_label=None,
                authority=authority,
                skip_reason=skip_reason,
                decision_kind=kind_raw or None,
                decision_reason=reason or None,
                hub_taxonomy_win=True,
            )
        if named and frigate:
            # Frigate may be a named label, but never a Hub taxonomy go-metric win.
            return RecognitionOutcome(
                kind=OutcomeKind.NAMED_ACCEPT,
                species_name=species,
                presence_label=None,
                authority="frigate",
                skip_reason=skip_reason,
                decision_kind=kind_raw or None,
                decision_reason=reason or None,
                hub_taxonomy_win=False,
            )
        # accepted_species / auto_accept with generic Bird/Unknown → presence.
        return RecognitionOutcome(
            kind=OutcomeKind.PRESENCE,
            species_name=None,
            presence_label=species or "Bird",
            authority=authority,
            skip_reason=skip_reason or "generic_labeled_as_accepted_species",
            decision_kind=kind_raw or None,
            decision_reason=reason or None,
            hub_taxonomy_win=False,
        )

    if named and not frigate:
        return RecognitionOutcome(
            kind=OutcomeKind.NAMED_ACCEPT,
            species_name=species,
            presence_label=None,
            authority=authority,
            skip_reason=skip_reason,
            decision_kind=kind_raw or None,
            decision_reason=reason or None,
            hub_taxonomy_win=True,
        )

    return RecognitionOutcome(
        kind=OutcomeKind.PRESENCE,
        species_name=None,
        presence_label=species or "Bird",
        authority=authority,
        skip_reason=skip_reason,
        decision_kind=kind_raw or None,
        decision_reason=reason or None,
        hub_taxonomy_win=False,
    )


def hub_taxonomy_wins(rows: list[Mapping[str, Any]] | None) -> int:
    """Count Hub-only named_accept outcomes (SOTA go numerator)."""
    n = 0
    for row in rows or []:
        if from_persist_row(row).hub_taxonomy_win:
            n += 1
    return n
