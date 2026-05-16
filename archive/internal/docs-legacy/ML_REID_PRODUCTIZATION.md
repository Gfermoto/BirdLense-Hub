# Re-ID Productization Plan (v1)

[Русский](./ML_REID_PRODUCTIZATION.ru.md)

Parent issue: [#390](https://github.com/Gfermoto/BirdLense-Hub/issues/390)

## Goal

Define safe product behavior for `same-individual` suggestions before any automated merge logic.

## Decision policy

Re-ID always emits one of:

- `suggest_same_individual`
- `inconclusive`
- `suggest_different_individual`

Auto-merge is disabled by default. Merge requires operator confirmation.

## Policy inputs

- cosine similarity score
- species match/mismatch
- camera id and time window
- embedding freshness and schema compatibility

## Safety rules

- reject cross-species merge suggestions
- require stronger thresholds for cross-camera suggestions
- suppress suggestion if embedding schema is mixed or stale
- limit aggressive recurrence by cooldown window per gallery identity

## Threshold strategy

- per-species threshold table (default + optional overrides)
- optional per-camera calibration offsets
- conservative fallback for unknown/new species

## Quality metrics

- `precision_at_1`
- `false_merge_rate`
- `coverage` (share of events with confident suggestion)

Gate for production enablement:

- no increase in false merges vs baseline
- precision/coverage improve or stay within pre-approved tolerance

## Validation strategy

1. offline evaluation on fixed labeled slice
2. shadow mode in production (no operator-facing merge action)
3. guarded UI suggestions with explicit confirm/reject
4. optional A/B on operator workload and correction outcomes

## Minimal UI scope

- System/Library status card:
  - embedding freshness
  - suggestion volume
  - reject/accept ratio
- review queue with decision audit trail

## Risk controls

- hard kill-switch for Re-ID suggestion flow
- rollback to read-only summary mode
- full decision trace export for incident review
