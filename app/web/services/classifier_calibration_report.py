"""Classifier calibration report from operator corrections (SOTA-16 / #507)."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CorrectionRow:
    from_name: str
    to_name: str
    confidence: float
    detection_provider: str | None
    source: str | None


def load_corrections_from_db(db_path: Path, *, limit: int = 10_000) -> list[CorrectionRow]:
    """Read species_correction rows from activity_log joined to video_species."""
    con = sqlite3.connect(f"file:{db_path.expanduser().resolve()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT al.data AS payload, vs.confidence AS confidence,
                   vs.detection_provider AS detection_provider
            FROM activity_log al
            JOIN video_species vs ON vs.id = CAST(json_extract(al.data, '$.detection_id') AS INTEGER)
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
        if not fr or not to or fr.lower() == to.lower():
            continue
        try:
            conf = float(row["confidence"] or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        out.append(
            CorrectionRow(
                from_name=fr,
                to_name=to,
                confidence=conf,
                detection_provider=(row["detection_provider"] or None),
                source=(payload.get("source") or None),
            ),
        )
    return out


def confusion_pair_counts(rows: list[CorrectionRow]) -> Counter[tuple[str, str]]:
    pairs: Counter[tuple[str, str]] = Counter()
    for r in rows:
        pairs[(r.from_name, r.to_name)] += 1
    return pairs


def _is_rodent_label(name: str) -> bool:
    n = (name or "").strip().lower()
    return any(x in n for x in ("mouse", "rodent", "squirrel", "rat", "vole", "мыш", "белк"))


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
            "not from an offline val-set sweep. Re-run after major model or allowlist changes."
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
        "0 = disabled. Start with 0.012–0.02 on wide-angle feeders if rodent→tit/confusion persists."
    )
    return rec


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
    return {
        "db": str(db_path),
        "corrections_analyzed": len(rows),
        "top_confusion_pairs": top_pairs,
        "corrections_by_source": dict(by_source),
        "threshold_recommendations": recommend_binary_thresholds(rows),
    }
