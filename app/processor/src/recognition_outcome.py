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

    _FALLBACK_PRESENCE_REASONS = frozenset(
        {
            "fallback_bird",
            "fallback_rodent",
            "fallback_squirrel",
            "fallback_detector_generic",
        }
    )
    if kind_raw in {"accepted_generic", "accepted_binary"} or reason in _FALLBACK_PRESENCE_REASONS:
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

    # Uncertain / needs_review named must never be a hub taxonomy win.
    needs_review = bool(row.get("classifier_needs_review"))
    if needs_review and named and kind_raw in {"accepted_species", ""} and not (
        kind_raw.startswith("review_only") or bucket == "review_only"
    ):
        return RecognitionOutcome(
            kind=OutcomeKind.REVIEW,
            species_name=species,
            presence_label=None,
            authority=authority,
            skip_reason=skip_reason or "classifier_needs_review",
            decision_kind=kind_raw or None,
            decision_reason=reason or None,
            hub_taxonomy_win=False,
        )

    if kind_raw == "accepted_species" or bucket == "auto_accept":
        if named and not frigate and not needs_review:
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
        if named and not frigate and needs_review:
            return RecognitionOutcome(
                kind=OutcomeKind.REVIEW,
                species_name=species,
                presence_label=None,
                authority=authority,
                skip_reason=skip_reason or "classifier_needs_review",
                decision_kind=kind_raw or None,
                decision_reason=reason or None,
                hub_taxonomy_win=False,
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

    # Named label without explicit accept contract is never a silent hub taxonomy win.
    return RecognitionOutcome(
        kind=OutcomeKind.PRESENCE,
        species_name=species if named else None,
        presence_label=None if named else (species or "Bird"),
        authority=authority,
        skip_reason=skip_reason
        or ("named_without_accept_contract" if named else None),
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


def stamp_recognition_outcome(
    row: dict[str, Any],
    *,
    birder_unknown_label: str | None = None,
) -> dict[str, Any]:
    """Attach RecognitionOutcome fields onto a persist/decision row (in-place)."""
    out = from_persist_row(row, birder_unknown_label=birder_unknown_label)
    row["recognition_kind"] = out.kind.value
    row["hub_taxonomy_win"] = bool(out.hub_taxonomy_win)
    row["recognition_authority"] = out.authority
    if out.skip_reason and not row.get("classify_skip_reason"):
        row["classify_skip_reason"] = out.skip_reason
    return row


def summarize_recognition_outcomes(
    rows: list[Mapping[str, Any]] | None,
    *,
    birder_unknown_label: str | None = None,
) -> dict[str, Any]:
    """Session-level taxonomy/presence breakdown for observability (RC9 thin)."""
    counts = {
        OutcomeKind.PRESENCE.value: 0,
        OutcomeKind.REVIEW.value: 0,
        OutcomeKind.NAMED_ACCEPT.value: 0,
        OutcomeKind.NAMED_REJECT.value: 0,
    }
    wins = 0
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        out = from_persist_row(row, birder_unknown_label=birder_unknown_label)
        counts[out.kind.value] = counts.get(out.kind.value, 0) + 1
        if out.hub_taxonomy_win:
            wins += 1
    return {
        "by_kind": counts,
        "hub_taxonomy_wins": wins,
        "taxonomy": {
            "hub_wins": wins,
            "named_accept": counts[OutcomeKind.NAMED_ACCEPT.value],
            "review": counts[OutcomeKind.REVIEW.value],
        },
        "presence": {
            "rows": counts[OutcomeKind.PRESENCE.value],
        },
    }
