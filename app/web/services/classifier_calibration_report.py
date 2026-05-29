"""Classifier calibration + consensus report from operator feedback (#520)."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class CorrectionRow:
    detection_id: int | None
    video_id: int | None
    track_id: int | None
    from_name: str
    to_name: str
    confidence: float
    detection_provider: str | None
    source: str | None
    classifier_entropy: float | None
    classifier_top1_top2_margin: float | None
    classifier_needs_review: bool
    review_reason: str | None

    @property
    def is_correct(self) -> bool:
        return self.from_name.strip().lower() == self.to_name.strip().lower()


def load_corrections_from_db(
    db_path: Path,
    *,
    limit: int = 10_000,
) -> list[CorrectionRow]:
    """Read species feedback rows from activity_log joined to video_species."""
    con = sqlite3.connect(
        f"file:{db_path.expanduser().resolve()}?mode=ro",
        uri=True,
    )
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT al.data AS payload,
                   CAST(
                     json_extract(al.data, '$.detection_id') AS INTEGER
                   ) AS detection_id,
                   vs.video_id AS video_id,
                   vs.track_id AS track_id,
                   vs.confidence AS confidence,
                   vs.detection_provider AS detection_provider,
                   vs.classifier_entropy AS classifier_entropy,
                   vs.classifier_top1_top2_margin
                     AS classifier_top1_top2_margin,
                   vs.classifier_needs_review AS classifier_needs_review,
                   vs.review_reason AS review_reason
            FROM activity_log al
            LEFT JOIN video_species vs
              ON vs.id = CAST(
                json_extract(al.data, '$.detection_id') AS INTEGER
              )
            WHERE al.type = 'species_correction'
            ORDER BY al.created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    finally:
        con.close()

    out: list[CorrectionRow] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        fr = (payload.get("from_species_name") or "").strip()
        to = (payload.get("to_species_name") or "").strip()
        if not fr or not to:
            continue
        try:
            conf = float(row["confidence"] or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        try:
            did = (
                int(row["detection_id"])
                if row["detection_id"] is not None
                else None
            )
        except (TypeError, ValueError):
            did = None
        try:
            vid = int(row["video_id"]) if row["video_id"] is not None else None
        except (TypeError, ValueError):
            vid = None
        try:
            tid = int(row["track_id"]) if row["track_id"] is not None else None
        except (TypeError, ValueError):
            tid = None
        try:
            entropy = (
                float(row["classifier_entropy"])
                if row["classifier_entropy"] is not None
                else None
            )
        except (TypeError, ValueError):
            entropy = None
        try:
            margin = (
                float(row["classifier_top1_top2_margin"])
                if row["classifier_top1_top2_margin"] is not None
                else None
            )
        except (TypeError, ValueError):
            margin = None
        out.append(
            CorrectionRow(
                detection_id=did,
                video_id=vid,
                track_id=tid,
                from_name=fr,
                to_name=to,
                confidence=conf,
                detection_provider=(row["detection_provider"] or None),
                source=(payload.get("source") or None),
                classifier_entropy=entropy,
                classifier_top1_top2_margin=margin,
                classifier_needs_review=bool(row["classifier_needs_review"]),
                review_reason=(row["review_reason"] or None),
            ),
        )
    return out


def confusion_pair_counts(rows: list[CorrectionRow]) -> Counter[tuple[str, str]]:
    pairs: Counter[tuple[str, str]] = Counter()
    for r in rows:
        if not r.is_correct:
            pairs[(r.from_name, r.to_name)] += 1
    return pairs


def _is_rodent_label(name: str) -> bool:
    n = (name or "").strip().lower()
    return any(
        x in n
        for x in (
            "mouse",
            "rodent",
            "squirrel",
            "rat",
            "vole",
            "мыш",
            "белк",
        )
    )


def _is_generic_bird_label(name: str) -> bool:
    n = (name or "").strip().lower()
    return n in ("bird", "unknown bird", "generic bird")


def recommend_binary_thresholds(rows: list[CorrectionRow]) -> dict[str, Any]:
    """Heuristic floors from operator corrections (not a full val-set sweep)."""
    rodent_as_bird = [
        r.confidence
        for r in rows
        if _is_rodent_label(r.from_name) and not _is_rodent_label(r.to_name)
    ]
    bird_as_other = [
        r.confidence
        for r in rows
        if _is_generic_bird_label(r.from_name) and not _is_generic_bird_label(r.to_name)
    ]
    all_conf = [r.confidence for r in rows if r.confidence > 0]

    def _pct(vals: list[float], q: float) -> float | None:
        if not vals:
            return None
        s = sorted(vals)
        idx = max(0, min(len(s) - 1, int(round((len(s) - 1) * q))))
        return round(float(s[idx]), 3)

    rec: dict[str, Any] = {
        "sample_corrections": len(rows),
        "notes": (
            "Recommendations are derived from operator corrections in activity_log, "
            "not from an offline val-set sweep. Re-run after major "
            "model or allowlist changes."
        ),
        "recommended_processor_yaml": {},
    }
    if rodent_as_bird:
        p75 = _pct(rodent_as_bird, 0.75) or 0.25
        rec["recommended_processor_yaml"]["min_confidence_binary_bird"] = round(
            min(0.45, max(0.12, p75 + 0.05)),
            3,
        )
        rec["rodent_misclassified_as_bird"] = {
            "count": len(rodent_as_bird),
            "confidence_p50": _pct(rodent_as_bird, 0.5),
            "confidence_p75": p75,
        }
    if bird_as_other:
        p75 = _pct(bird_as_other, 0.75) or 0.22
        rec["recommended_processor_yaml"]["min_confidence_binary"] = round(
            min(0.5, max(0.10, p75)),
            3,
        )
    if all_conf:
        rec["correction_confidence_p75"] = _pct(all_conf, 0.75)
    rec["recommended_processor_yaml"].setdefault(
        "bird_skip_classifier_max_area_frac",
        0.015,
    )
    rec["bird_skip_classifier_doc"] = (
        "Skip Birder on huge «Bird» boxes (area fraction of frame). "
        "0 = disabled. Start with 0.012–0.02 on wide-angle feeders "
        "if rodent→tit/confusion persists."
    )
    incorrect_conf = [
        r.confidence
        for r in rows
        if not r.is_correct and r.confidence > 0
    ]
    if incorrect_conf:
        p75 = _pct(incorrect_conf, 0.75) or 0.48
        rec["recommended_processor_yaml"]["unknown_confidence_threshold"] = round(
            min(0.9, max(0.3, p75)),
            3,
        )
    return rec


def _calibration_metrics(
    rows: list[CorrectionRow],
    *,
    n_bins: int = 10,
) -> dict[str, Any]:
    valid = [r for r in rows if 0.0 <= r.confidence <= 1.0]
    if not valid:
        return {
            "samples": 0,
            "ece": None,
            "brier": None,
            "reliability_bins": [],
        }
    bin_count = max(2, min(int(n_bins or 10), 30))
    bins: list[list[CorrectionRow]] = [[] for _ in range(bin_count)]
    for r in valid:
        idx = min(bin_count - 1, int(r.confidence * bin_count))
        bins[idx].append(r)
    reliability_bins: list[dict[str, Any]] = []
    total = float(len(valid))
    ece = 0.0
    brier_sum = 0.0
    for idx, group in enumerate(bins):
        lo = idx / float(bin_count)
        hi = (idx + 1) / float(bin_count)
        if not group:
            reliability_bins.append(
                {
                    "bin_index": idx,
                    "lo": round(lo, 4),
                    "hi": round(hi, 4),
                    "count": 0,
                    "avg_confidence": None,
                    "accuracy": None,
                }
            )
            continue
        avg_conf = mean(r.confidence for r in group)
        accuracy = mean(1.0 if r.is_correct else 0.0 for r in group)
        weight = len(group) / total
        ece += abs(accuracy - avg_conf) * weight
        for r in group:
            y = 1.0 if r.is_correct else 0.0
            brier_sum += (r.confidence - y) ** 2
        reliability_bins.append(
            {
                "bin_index": idx,
                "lo": round(lo, 4),
                "hi": round(hi, 4),
                "count": len(group),
                "avg_confidence": round(float(avg_conf), 6),
                "accuracy": round(float(accuracy), 6),
            }
        )
    return {
        "samples": len(valid),
        "ece": round(float(ece), 6),
        "brier": round(float(brier_sum / total), 6),
        "reliability_bins": reliability_bins,
    }


def _topk_unknown_metrics(
    rows: list[CorrectionRow],
    *,
    unknown_threshold: float = 0.48,
    top3_margin_proxy_threshold: float = 0.08,
) -> dict[str, Any]:
    if not rows:
        return {
            "samples": 0,
            "top1_before": None,
            "top3_proxy_before": None,
            "top1_after_unknown_policy": None,
            "top3_proxy_after_unknown_policy": None,
            "false_species_rate_before": None,
            "false_species_rate_after_unknown_policy": None,
            "unknown_share_after_policy": None,
        }
    total = len(rows)
    correct_before = sum(1 for r in rows if r.is_correct)
    top3_hits_before = 0
    for r in rows:
        if r.is_correct:
            top3_hits_before += 1
            continue
        m = r.classifier_top1_top2_margin
        if m is not None and float(m) <= float(top3_margin_proxy_threshold):
            top3_hits_before += 1
    known = [r for r in rows if r.confidence >= float(unknown_threshold)]
    unknown = [r for r in rows if r.confidence < float(unknown_threshold)]
    known_total = len(known)
    known_correct = sum(1 for r in known if r.is_correct)
    known_top3 = 0
    for r in known:
        if r.is_correct:
            known_top3 += 1
            continue
        m = r.classifier_top1_top2_margin
        if m is not None and float(m) <= float(top3_margin_proxy_threshold):
            known_top3 += 1
    known_errors = max(0, known_total - known_correct)
    return {
        "samples": total,
        "top1_before": round(correct_before / float(total), 6),
        "top3_proxy_before": round(top3_hits_before / float(total), 6),
        "top1_after_unknown_policy": (
            round(known_correct / float(known_total), 6)
            if known_total > 0
            else None
        ),
        "top3_proxy_after_unknown_policy": (
            round(known_top3 / float(known_total), 6)
            if known_total > 0
            else None
        ),
        "false_species_rate_before": round(
            (total - correct_before) / float(total),
            6,
        ),
        "false_species_rate_after_unknown_policy": (
            round(known_errors / float(known_total), 6)
            if known_total > 0
            else None
        ),
        "unknown_share_after_policy": round(len(unknown) / float(total), 6),
    }


def _session_consensus_metrics(
    rows: list[CorrectionRow],
    *,
    min_support: int = 2,
    min_ratio: float = 0.55,
) -> dict[str, Any]:
    per_video: dict[int, list[CorrectionRow]] = {}
    for r in rows:
        if r.video_id is None:
            continue
        per_video.setdefault(int(r.video_id), []).append(r)
    sessions: list[dict[str, Any]] = []
    passed = 0
    for video_id, group in sorted(per_video.items()):
        votes: dict[str, float] = {}
        for r in group:
            label = r.to_name.strip()
            if not label:
                continue
            votes[label] = votes.get(label, 0.0) + max(0.01, r.confidence)
        if not votes:
            continue
        ordered = sorted(votes.items(), key=lambda x: x[1], reverse=True)
        winner, winner_weight = ordered[0]
        total_weight = sum(votes.values())
        ratio = winner_weight / total_weight if total_weight > 0 else 0.0
        support = sum(
            1
            for r in group
            if r.to_name.strip().lower() == winner.lower()
        )
        ok = support >= int(min_support) and ratio >= float(min_ratio)
        if ok:
            passed += 1
        sessions.append(
            {
                "video_id": int(video_id),
                "consensus_species": winner,
                "support_count": int(support),
                "weighted_ratio": round(float(ratio), 6),
                "rows_total": len(group),
                "consensus_ready": ok,
            }
        )
    return {
        "sessions_total": len(sessions),
        "sessions_consensus_ready": passed,
        "consensus_ready_ratio": (
            round(passed / float(len(sessions)), 6)
            if sessions
            else None
        ),
        "sessions": sessions[:200],
    }


def _ood_guardrail_metrics(
    rows: list[CorrectionRow],
    *,
    entropy_threshold: float = 1.1,
    margin_threshold: float = 0.02,
) -> dict[str, Any]:
    if not rows:
        return {
            "samples": 0,
            "flagged_count": 0,
            "flagged_share": None,
            "incorrect_in_flagged_share": None,
            "flag_precision_for_errors": None,
        }
    flagged = 0
    incorrect_flagged = 0
    incorrect_total = 0
    for r in rows:
        is_incorrect = not r.is_correct
        if is_incorrect:
            incorrect_total += 1
        reason = str(r.review_reason or "").strip().lower()
        ood_by_reason = reason in {
            "classifier_uncertainty",
            "ood_candidate",
            "open_set_candidate",
        }
        by_entropy = (
            r.classifier_entropy is not None
            and float(r.classifier_entropy) >= float(entropy_threshold)
        )
        by_margin = (
            r.classifier_top1_top2_margin is not None
            and float(r.classifier_top1_top2_margin) <= float(margin_threshold)
        )
        is_flagged = bool(
            r.classifier_needs_review
            or ood_by_reason
            or by_entropy
            or by_margin
        )
        if not is_flagged:
            continue
        flagged += 1
        if is_incorrect:
            incorrect_flagged += 1
    total = len(rows)
    return {
        "samples": total,
        "flagged_count": flagged,
        "flagged_share": round(flagged / float(total), 6),
        "incorrect_in_flagged_share": (
            round(incorrect_flagged / float(flagged), 6)
            if flagged > 0
            else None
        ),
        "flag_precision_for_errors": (
            round(incorrect_flagged / float(incorrect_total), 6)
            if incorrect_total > 0
            else None
        ),
    }


def _long_tail_report(
    rows: list[CorrectionRow],
    *,
    min_samples: int = 3,
) -> dict[str, Any]:
    by_target: dict[str, dict[str, int]] = {}
    for r in rows:
        key = r.to_name.strip() or "unknown"
        bucket = by_target.setdefault(key, {"total": 0, "errors": 0})
        bucket["total"] += 1
        if not r.is_correct:
            bucket["errors"] += 1
    classes = []
    for name, s in by_target.items():
        if s["total"] < int(min_samples):
            continue
        classes.append(
            {
                "species": name,
                "samples": int(s["total"]),
                "error_rate_before": round(s["errors"] / float(s["total"]), 6),
            }
        )
    classes.sort(
        key=lambda x: (x["error_rate_before"], x["samples"]),
        reverse=True,
    )
    return {
        "classes_min_samples": int(min_samples),
        "class_count": len(classes),
        "classes": classes[:200],
    }


def build_report(db_path: Path, *, pair_limit: int = 15) -> dict[str, Any]:
    rows = load_corrections_from_db(db_path)
    pairs = confusion_pair_counts(rows)
    by_source: Counter[str] = Counter()
    for r in rows:
        by_source[r.source or "unknown"] += 1
    top_pairs = [
        {"from": fr, "to": to, "count": cnt}
        for (fr, to), cnt in pairs.most_common(pair_limit)
    ]
    calibration_metrics = _calibration_metrics(rows)
    topk_metrics = _topk_unknown_metrics(rows)
    ood_guardrail = _ood_guardrail_metrics(rows)
    session_consensus = _session_consensus_metrics(rows)
    long_tail = _long_tail_report(rows)
    return {
        "db": str(db_path),
        "corrections_analyzed": len(rows),
        "top_confusion_pairs": top_pairs,
        "corrections_by_source": dict(by_source),
        "threshold_recommendations": recommend_binary_thresholds(rows),
        "calibration_metrics": calibration_metrics,
        "topk_metrics": topk_metrics,
        "session_consensus": session_consensus,
        "unknown_ood_dashboard": {
            "unknown_policy": {
                "threshold": 0.48,
                "unknown_share_after_policy": topk_metrics.get(
                    "unknown_share_after_policy"
                ),
                "false_species_rate_before": topk_metrics.get(
                    "false_species_rate_before"
                ),
                "false_species_rate_after_unknown_policy": (
                    topk_metrics.get("false_species_rate_after_unknown_policy")
                ),
            },
            "ood_guardrail": ood_guardrail,
        },
        "long_tail_report": long_tail,
        "notes": {
            "top3_is_proxy": (
                "Top-3 uses margin proxy from classifier_top1_top2_margin; "
                "for exact Top-3 run full truth-set export."
            )
        },
    }
