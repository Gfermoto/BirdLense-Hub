"""Deterministic arbitration layer for final clip detections."""

from __future__ import annotations

from typing import Iterable

from decision_outcome import compute_outcome_bucket
from species_normalizer import _extract_common_for_merge

GENERIC_BIRD_NAME = "Bird"
ARBITRATION_SCORE_GAP = 0.12
ARBITRATION_MIN_SUPPORTS = 2
ARBITRATION_CONFLICT_OVERLAP_SEC = 3.0
ARBITRATION_GENERIC_ABSORB_OVERLAP_SEC = 1.0
ARBITRATION_WEAK_CONFLICT_MAX_SCORE = 0.62
ARBITRATION_FRIGATE_STANDALONE_ABSORB_MIN_CONF = 0.82
ARBITRATION_FRIGATE_STANDALONE_ABSORB_MIN_RATIO = 0.95
ARBITRATION_VISUAL_ANCHOR_SCORE = 0.62
ARBITRATION_VISUAL_ANCHOR_CONF = 0.46


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _canonical_species_key(row: dict) -> str:
    species_name = row.get("species_name") or row.get("species") or ""
    return _extract_common_for_merge(str(species_name or ""))


def _is_generic_bird(row: dict) -> bool:
    return _canonical_species_key(row) == "bird"


def _is_rodent_like(row: dict) -> bool:
    key = _canonical_species_key(row)
    return any(token in key for token in ("squirrel", "chipmunk", "rodent", "sciurus", "грызун"))


def _is_specific_bird(row: dict) -> bool:
    key = _canonical_species_key(row)
    return bool(key) and key != "bird" and not _is_rodent_like(row)


def _overlap_seconds(a: dict, b: dict) -> float:
    start = max(_safe_float(a.get("start_time")), _safe_float(b.get("start_time")))
    end = min(_safe_float(a.get("end_time")), _safe_float(b.get("end_time")))
    return end - start


def _duration_seconds(row: dict) -> float:
    return max(0.0, _safe_float(row.get("end_time")) - _safe_float(row.get("start_time")))


def _is_frigate_standalone_row(row: dict) -> bool:
    provider = str(row.get("detection_provider") or "").strip().lower()
    kind = str(row.get("decision_kind") or "").strip().lower()
    return provider == "frigate" and kind in {"frigate_standalone", "frigate_standalone_excluded"}


def _can_absorb_frigate_standalone_generic(generic: dict, specific: dict) -> bool:
    if not (_is_generic_bird(generic) and _is_specific_bird(specific)):
        return False
    if not (_is_frigate_standalone_row(generic) and _is_frigate_standalone_row(specific)):
        return False
    overlap = _overlap_seconds(generic, specific)
    if overlap < ARBITRATION_GENERIC_ABSORB_OVERLAP_SEC:
        return False
    shorter = min(_duration_seconds(generic), _duration_seconds(specific))
    if shorter > 0 and (overlap / shorter) < ARBITRATION_FRIGATE_STANDALONE_ABSORB_MIN_RATIO:
        return False
    return _safe_float(specific.get("confidence")) >= ARBITRATION_FRIGATE_STANDALONE_ABSORB_MIN_CONF


def _support_count(row: dict) -> int:
    supports = 0
    if str(row.get("decision_kind") or "").strip().lower() == "accepted_species":
        supports += 1
    if _safe_float(row.get("classifier_confidence")) >= 0.45:
        supports += 1
    if str(row.get("audio_evidence") or "").strip().lower() == "support":
        supports += 1
    if bool(row.get("_multi_camera_support")):
        supports += 1
    providers = {
        str(provider).strip().lower() for provider in (row.get("contributing_providers") or []) if str(provider).strip()
    }
    provider = str(row.get("detection_provider") or "").strip().lower()
    if provider:
        providers.add(provider)
    if "frigate" in providers or str(row.get("decision_reason") or "").strip().lower() == "promoted_by_frigate":
        supports += 1
    return supports


def _has_visual_anchor(row: dict) -> bool:
    lineage = {
        str(provider).strip().lower()
        for provider in (row.get("contributing_providers") or [])
        if str(provider).strip()
    }
    provider = str(row.get("detection_provider") or "").strip().lower()
    if provider and provider != "arbitration":
        lineage.add(provider)
    if "yolo" in lineage:
        return True
    try:
        return int(row.get("track_id") or 0) > 0
    except (TypeError, ValueError):
        return False


def _arbitration_score(row: dict) -> float:
    return (
        _safe_float(row.get("confidence"))
        + (0.08 * float(_support_count(row)))
        + (0.02 * min(1.0, _safe_float(row.get("_birdnet_prior"))))
    )


def _row_tie_break_key(row: dict) -> tuple:
    species_key = _canonical_species_key(row)
    track_id_raw = row.get("track_id")
    try:
        track_id = int(track_id_raw)
    except (TypeError, ValueError):
        track_id = -1
    return (species_key, track_id)


def _rank_key(row: dict) -> tuple:
    return (
        _arbitration_score(row),
        _support_count(row),
        _safe_float(row.get("confidence")),
        _row_tie_break_key(row),
    )


def _tag_row(row: dict, reason: str) -> None:
    previous_reason = row.get("decision_reason")
    if previous_reason and previous_reason != reason and "decision_reason_before_arbitration" not in row:
        row["decision_reason_before_arbitration"] = previous_reason
    row["decision_reason"] = reason
    row["arbitration_reason"] = reason
    tag = str(row.get("_fusion_used") or "").strip()
    row["_fusion_used"] = f"{tag}+{reason}" if tag else reason


def _sync_outcome_bucket(row: dict) -> dict:
    row["accepted"] = bool(row.get("accepted", True))
    row["visit_eligible"] = bool(row.get("visit_eligible", True))
    row["outcome_bucket"] = compute_outcome_bucket(
        accepted=bool(row.get("accepted", True)),
        visit_eligible=bool(row.get("visit_eligible", True)),
        decision_kind=str(row.get("decision_kind") or ""),
    )
    return row


def _merge_provider_sets(rows: Iterable[dict]) -> list[str]:
    providers = set()
    for row in rows:
        provider = str(row.get("detection_provider") or "").strip()
        if provider:
            providers.add(provider)
        providers.update(str(item).strip() for item in (row.get("contributing_providers") or []) if str(item).strip())
    return sorted(providers)


def _build_generic_review_row(
    rows: list[dict],
    *,
    reason: str = "downgraded_to_generic_due_to_conflict",
) -> dict:
    leader = max(rows, key=_rank_key)
    start_time = min(_safe_float(row.get("start_time")) for row in rows)
    end_time = max(_safe_float(row.get("end_time")) for row in rows)
    review_row = dict(leader)
    review_row["species_name"] = GENERIC_BIRD_NAME
    review_row["species"] = GENERIC_BIRD_NAME
    review_row["start_time"] = start_time
    review_row["end_time"] = end_time
    review_row["track_id"] = None
    review_row["visit_eligible"] = False
    review_row["notification_eligible"] = False
    review_row["decision_kind"] = "review_only_generic"
    review_row["evidence_state"] = "cross_species_conflict"
    review_row["detection_provider"] = "arbitration"
    review_row["contributing_providers"] = _merge_provider_sets(rows)
    review_row["confidence"] = max(_safe_float(leader.get("confidence")), 0.45)
    review_row["_pre_fusion_confidence"] = _safe_float(review_row.get("confidence"))
    _tag_row(review_row, reason)
    return _sync_outcome_bucket(review_row)


def _absorb_generic_bird(rows: list[dict]) -> list[dict]:
    kept = list(rows)
    to_drop: set[int] = set()
    for index, row in enumerate(kept):
        if not _is_generic_bird(row):
            continue
        generic_score = _arbitration_score(row)
        winner_idx = None
        winner_score = generic_score
        winner_reason = "absorbed_generic_into_species"
        for other_index, other in enumerate(kept):
            if index == other_index or other_index in to_drop:
                continue
            if not _is_specific_bird(other):
                continue
            if _overlap_seconds(row, other) < ARBITRATION_GENERIC_ABSORB_OVERLAP_SEC:
                continue
            other_score = _arbitration_score(other)
            other_tie_break = _row_tie_break_key(other)
            winner_tie_break = (
                _row_tie_break_key(kept[winner_idx]) if winner_idx is not None else _row_tie_break_key(row)
            )
            if _can_absorb_frigate_standalone_generic(row, other) and (
                other_score > winner_score or (other_score == winner_score and other_tie_break > winner_tie_break)
            ):
                winner_idx = other_index
                winner_score = other_score
                winner_reason = "absorbed_generic_into_frigate_species"
                continue
            if _support_count(other) >= ARBITRATION_MIN_SUPPORTS and (
                other_score > winner_score or (other_score == winner_score and other_tie_break > winner_tie_break)
            ):
                winner_idx = other_index
                winner_score = other_score
        if winner_idx is not None:
            to_drop.add(index)
            _tag_row(kept[winner_idx], winner_reason)
    return [row for idx, row in enumerate(kept) if idx not in to_drop]


def _drop_clip_level_generic_bird_when_species_present(rows: list[dict]) -> list[dict]:
    """Clip-level product rule: if specific bird exists, hide generic Bird rows."""
    if not rows:
        return rows
    has_specific = any(_is_specific_bird(row) for row in rows)
    if not has_specific:
        return rows
    out: list[dict] = []
    for row in rows:
        if _is_generic_bird(row):
            continue
        out.append(row)
    return out


def _connected_conflict_groups(rows: list[dict]) -> list[list[int]]:
    edges: dict[int, set[int]] = {idx: set() for idx in range(len(rows))}
    for left_idx, left in enumerate(rows):
        if not _is_specific_bird(left):
            continue
        for right_idx in range(left_idx + 1, len(rows)):
            right = rows[right_idx]
            if not _is_specific_bird(right):
                continue
            if _canonical_species_key(left) == _canonical_species_key(right):
                continue
            if _overlap_seconds(left, right) >= ARBITRATION_CONFLICT_OVERLAP_SEC:
                edges[left_idx].add(right_idx)
                edges[right_idx].add(left_idx)
    groups: list[list[int]] = []
    seen: set[int] = set()
    for start_idx, linked in edges.items():
        if start_idx in seen or not linked:
            continue
        stack = [start_idx]
        group: list[int] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            group.append(current)
            stack.extend(edges[current] - seen)
        if len(group) > 1:
            groups.append(sorted(group))
    return groups


def apply_hypothesis_arbitration(detections: list[dict]) -> list[dict]:
    """Collapse generic/species conflicts and choose one strong species when justified."""
    if len(detections or []) < 2:
        return [_sync_outcome_bucket(row) for row in list(detections or [])]

    rows = _absorb_generic_bird(list(detections))
    rows = _drop_clip_level_generic_bird_when_species_present(rows)
    groups = _connected_conflict_groups(rows)
    if not groups:
        return [_sync_outcome_bucket(row) for row in rows]

    replacements: dict[int, dict | None] = {}
    for group in groups:
        candidates = [rows[idx] for idx in group]
        ranked = sorted(
            candidates,
            key=_rank_key,
            reverse=True,
        )
        winner = ranked[0]
        runner = ranked[1]
        winner_score = _arbitration_score(winner)
        runner_score = _arbitration_score(runner)
        score_gap = winner_score - runner_score
        winner_supports = _support_count(winner)

        if winner_supports >= ARBITRATION_MIN_SUPPORTS and score_gap >= ARBITRATION_SCORE_GAP:
            _tag_row(winner, "species_won_by_multi_source_consensus")
            winner["visit_eligible"] = True
            winner["notification_eligible"] = bool(winner.get("notification_eligible", True))
            _sync_outcome_bucket(winner)
            for idx in group:
                replacements[idx] = winner if rows[idx] is winner else None
            continue

        if (
            _has_visual_anchor(winner)
            and winner_score >= ARBITRATION_VISUAL_ANCHOR_SCORE
            and _safe_float(winner.get("confidence")) >= ARBITRATION_VISUAL_ANCHOR_CONF
            and score_gap >= (ARBITRATION_SCORE_GAP * 0.5)
        ):
            _tag_row(winner, "species_kept_by_visual_anchor")
            winner["visit_eligible"] = True
            winner["notification_eligible"] = bool(winner.get("notification_eligible", True))
            _sync_outcome_bucket(winner)
            for idx in group:
                replacements[idx] = winner if rows[idx] is winner else None
            continue

        max_score = max(_arbitration_score(row) for row in candidates)
        max_supports = max(_support_count(row) for row in candidates)
        if max_score <= ARBITRATION_WEAK_CONFLICT_MAX_SCORE and max_supports < ARBITRATION_MIN_SUPPORTS:
            review_row = _build_generic_review_row(candidates)
            for idx in group:
                replacements[idx] = review_row if rows[idx] is winner else None
            continue

        review_row = _build_generic_review_row(
            candidates,
            reason="downgraded_to_generic_due_to_strong_conflict",
        )
        for idx in group:
            replacements[idx] = review_row if rows[idx] is winner else None

    if not replacements:
        return [_sync_outcome_bucket(row) for row in rows]

    out: list[dict] = []
    seen_ids: set[int] = set()
    for idx, row in enumerate(rows):
        if idx not in replacements:
            out.append(row)
            continue
        replacement = replacements[idx]
        if replacement is None:
            continue
        marker = id(replacement)
        if marker in seen_ids:
            continue
        seen_ids.add(marker)
        out.append(replacement)
    for row in out:
        _sync_outcome_bucket(row)
    return out
