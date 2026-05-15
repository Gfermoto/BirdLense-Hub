# BirdLense Hub Domain Contract

[Русский](./DOMAIN_CONTRACT.ru.md)

---

This document defines the core invariants that keep BirdLense scientifically interpretable and operationally stable.

## Core entities

| Entity | Meaning | Source of truth |
|--------|---------|-----------------|
| `motion event` | Event that starts the recording loop | processor motion detector / MQTT |
| `recording session` | One `motion -> capture -> finalize` cycle | `app/processor/src/recording_session.py` |
| `clip` / `Video` | Physical recording file plus DB row | `video.mp4` + `Video` |
| `VideoSpecies` | Normalized detection inside a clip | `app/web/models.py` |
| `SpeciesVisit` | Logical species presence window across one or more clips | `app/web/services/visit_processor.py` |
| `review-only detection` | Human-reviewable detection that must not count as a visit | `visit_eligible = false` |
| `SpeciesTaxon` | Canonical species record | `species_taxon` |
| `SpeciesAlias` | Historical or localized name resolved to a taxon | `species_alias` |

## Time layers

BirdLense operates with three distinct time layers:

1. `trigger-time` — when the motion source started the session.
2. `clip-time` — physical bounds of the recorded file.
3. `visit-time` — logical presence window after deduplication.

They do not need to be identical, but they must remain explainable.

## Recording and visit invariants

- One `Video` may contain several `VideoSpecies` rows.
- One `SpeciesVisit` may span detections from several `Video` rows.
- A `review-only detection` must **not** create a `SpeciesVisit`.
- `VideoSpecies.species_visit_id is NULL` is expected for review-only rows.
- An orphan `SpeciesVisit` without linked `VideoSpecies` is a contract violation.
- Two clips of the same species with a tiny gap are treated as duplicate-clip candidates and must stay observable.

## Auto-decision invariants

Every final hypothesis emitted by the processor pipeline must expose:

- `decision_kind`
- `decision_reason`
- `accepted`
- `visit_eligible`
- `notification_eligible`
- `trust_band`
- cross-source evidence markers such as `audio_evidence` and fusion/arbitration metadata when present

Each outcome must clearly land in one of three buckets:

- `auto-accept`
- `review-only`
- `reject`

If overlapping species hypotheses stay in strong conflict and no winner is justified by
multi-source consensus, the pipeline must downgrade them to a single `review-only`
generic bird row instead of silently keeping multiple competing visit-eligible species rows.

## Species registry invariants

- `Species` is the UI-facing and historical row.
- `SpeciesTaxon` is the canonical entity.
- `SpeciesAlias` is the normalization layer.
- Multiple UI names are allowed only when they intentionally represent different entities, not accidental localization drift.
- Any unresolved name must be captured in `SpeciesUnresolvedName`.

## Baseline quality metrics

The contract snapshot is exposed at `GET /api/ui/system/domain-health`:

- `orphaned_visits`
- `visit_species_mismatches`
- `duplicate_name_group_count`
- `large_gap_visits`
- `review_only_video_detections`
- `unresolved_species_names`
- `duplicate_clip_candidates_24h`

These are operational quality gates, not cosmetic telemetry.
