# Action Recognition Plan (v1)

[Русский](./ML_ACTION_RECOGNITION_PLAN.ru.md)

Parent issue: [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392)
Related: [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379)

## Label taxonomy v1

- `arrival`
- `departure`
- `possible_feeding`

Extension-ready labels (next phase):

- `drinking`
- `aggression`
- `nesting_behavior`

## Dataset spec (v1)

Unit of annotation: action segment over track-aligned clip.

Required fields:

- `video_id`
- `track_id`
- `camera_id`
- `action_label`
- `t_start_ms`
- `t_end_ms`
- `confidence` (annotator confidence)
- `annotator_id`
- `created_at_utc`

Storage format for training: JSONL + manifest with schema version.

## Labeling guideline

- minimum segment length: 300 ms
- overlap allowed only if semantic actions are genuinely concurrent
- `arrival` and `departure` are boundary events: use tight windows
- `possible_feeding` requires visible feeder interaction or weight-correlated proxy

Inter-annotator agreement:

- target Cohen kappa >= 0.75 on calibration subset
- disagreement queue reviewed weekly

## Baseline model plan

Stage A:

- temporal head over existing track clips (lightweight baseline)

Stage B:

- clip model baseline (for example VideoMAE/TSN family) on curated subset

Stage C:

- compare temporal head vs clip model on same eval slices

## Compute budget (initial)

- annotation bootstrap: 2-3 operator-days for seed set
- baseline training: 1x GPU 24 GB, up to 12 hours per candidate
- evaluation/ablation: up to 6 hours additional GPU time

## Integration constraints

- action head must not reduce detector/classifier throughput
- if action model is unavailable, weak-label API path remains active
- action output is additive; never blocks species inference

## Quality bar for first production trial

- event-based F1 >= 0.70 on validation slices
- boundary delay p95 <= 1.5 s
- false positives per hour <= agreed threshold from operator baseline
