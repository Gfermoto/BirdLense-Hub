"""Helpers for stable decision outcome buckets across processor stages."""

from __future__ import annotations


def compute_outcome_bucket(
    *,
    accepted: bool,
    visit_eligible: bool = True,
    decision_kind: str | None = None,
) -> str:
    kind = str(decision_kind or '').strip().lower()
    if not accepted or kind == 'rejected':
        return 'rejected'
    if not visit_eligible or kind.startswith('review_only'):
        return 'review_only'
    return 'auto_accept'
