#!/usr/bin/env python3
"""Prepare ReID dataset grouped by global bird_profile_id."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReIdSample:
    video_species_id: int
    video_id: int
    species_id: int | None
    bird_profile_id: int
    track_id: int | None
    frames: str | None
    confidence: float | None
    classifier_needs_review: bool
    review_reason: str | None
    priority: int


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_manifest(db_path: Path, *, min_samples_per_profile: int = 2) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
          vs.id AS video_species_id,
          vs.video_id AS video_id,
          vs.species_id AS species_id,
          vs.bird_profile_id AS bird_profile_id,
          vs.track_id AS track_id,
          vs.frames AS frames,
          vs.confidence AS confidence,
          COALESCE(vs.classifier_needs_review, 0) AS classifier_needs_review,
          vs.review_reason AS review_reason,
          CASE
            WHEN EXISTS (
              SELECT 1
              FROM active_learning_case alc
              WHERE alc.video_species_id = vs.id
                AND (
                  alc.reason_code = 'semantic_review_required'
                  OR alc.status = 'semantic_review_required'
                )
            ) THEN 0
            WHEN COALESCE(vs.classifier_needs_review, 0) = 1 THEN 1
            ELSE 2
          END AS priority
        FROM video_species vs
        WHERE vs.bird_profile_id IS NOT NULL
        ORDER BY vs.bird_profile_id, priority, vs.id
        """
    ).fetchall()
    conn.close()

    grouped: dict[int, list[ReIdSample]] = {}
    for row in rows:
        sample = ReIdSample(
            video_species_id=int(row["video_species_id"]),
            video_id=int(row["video_id"]),
            species_id=int(row["species_id"]) if row["species_id"] is not None else None,
            bird_profile_id=int(row["bird_profile_id"]),
            track_id=int(row["track_id"]) if row["track_id"] is not None else None,
            frames=row["frames"],
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            classifier_needs_review=bool(row["classifier_needs_review"]),
            review_reason=row["review_reason"],
            priority=int(row["priority"]),
        )
        grouped.setdefault(sample.bird_profile_id, []).append(sample)

    identities = []
    for profile_id, samples in grouped.items():
        if len(samples) < min_samples_per_profile:
            continue
        identities.append(
            {
                "bird_profile_id": profile_id,
                "samples": [
                    {
                        "video_species_id": s.video_species_id,
                        "video_id": s.video_id,
                        "species_id": s.species_id,
                        "track_id": s.track_id,
                        "frames": json.loads(s.frames) if s.frames else None,
                        "confidence": s.confidence,
                        "classifier_needs_review": s.classifier_needs_review,
                        "review_reason": s.review_reason,
                        "priority": s.priority,
                    }
                    for s in samples
                ],
            }
        )

    triplets = []
    profile_ids = [item["bird_profile_id"] for item in identities]
    negatives = {pid: [x for x in profile_ids if x != pid] for pid in profile_ids}
    for identity in identities:
        pid = identity["bird_profile_id"]
        samples = identity["samples"]
        if len(samples) < 2 or not negatives[pid]:
            continue
        negative_profile = negatives[pid][0]
        negative_sample = next(
            s
            for other in identities
            if other["bird_profile_id"] == negative_profile
            for s in other["samples"]
        )
        triplets.append(
            {
                "anchor": samples[0]["video_species_id"],
                "positive": samples[1]["video_species_id"],
                "negative": negative_sample["video_species_id"],
                "anchor_profile_id": pid,
                "negative_profile_id": negative_profile,
            }
        )

    return {
        "schema": "reid_dataset_manifest@v1",
        "source": str(db_path),
        "profiles_count": len(identities),
        "triplets_count": len(triplets),
        "identities": identities,
        "triplets": triplets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ReID manifest grouped by bird_profile_id.")
    parser.add_argument("--db", required=True, help="Path to birdlense sqlite DB")
    parser.add_argument("--out", required=True, help="Output JSON file")
    parser.add_argument("--min-samples-per-profile", type=int, default=2)
    args = parser.parse_args()

    manifest = build_manifest(
        Path(args.db),
        min_samples_per_profile=max(2, int(args.min_samples_per_profile)),
    )
    out_path = Path(args.out)
    _ensure_parent(out_path)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[reid] wrote manifest: {out_path} (profiles={manifest['profiles_count']}, triplets={manifest['triplets_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

