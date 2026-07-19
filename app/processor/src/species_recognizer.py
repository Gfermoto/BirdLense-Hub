"""SpeciesRecognizer product facade (RC1 radical split).

Owns Hub taxonomy: named_accept, hub_taxonomy_wins, classifier skip reasons.
Does **not** own YOLO presence persist — see ``presence_recorder``.
"""

from __future__ import annotations

from typing import Any, Mapping


def summarize_taxonomy(
    *,
    visit_quality: Mapping[str, Any] | None = None,
    recognition_outcomes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact taxonomy KPI blob for session_summary.taxonomy."""
    vq = visit_quality if isinstance(visit_quality, Mapping) else {}
    outcomes = recognition_outcomes if isinstance(recognition_outcomes, Mapping) else {}
    return {
        "schema": "species_recognizer@v1",
        "hub_wins": int(vq.get("hub_taxonomy_wins") or 0),
        "named_share_hub": vq.get("named_share_hub"),
        "auto_accept_rows": int(vq.get("auto_accept_rows") or 0),
        "review_only_rows": int(vq.get("review_only_rows") or 0),
        "outcome_counts": dict(outcomes.get("by_kind") or outcomes.get("counts") or {}),
    }


def is_hub_taxonomy_win(row: Mapping[str, Any] | None) -> bool:
    from recognition_outcome import from_persist_row

    return bool(from_persist_row(row).hub_taxonomy_win)
