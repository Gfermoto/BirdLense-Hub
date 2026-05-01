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

## Execution backlog (issue-driven)

Status mapping:

- [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392): protocol/dataset/metrics.
- [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379): model selection, training, integration, rollout.

### Phase E0 — protocol freeze (#392)

- freeze taxonomy/guideline without ambiguity in docs;
- run `make ml-verify-action-labeling` on snapshot payload in local/CI flow;
- verify gate fails on intentionally broken payload (negative smoke).

DoD E0:

- `make ml-verify-action-labeling ACTION_EVENTS=<fixture>` passes on valid fixture;
- negative fixture deterministically fails;
- issue #392 includes command logs and fixture commit link.

### Phase E1 — dataset bootstrap (#392 -> #379)

- collect a seed set of action segments following current protocol;
- run calibration with double annotation;
- capture inter-annotator agreement and disagreement queue.

DoD E1:

- seed manifest is published (volume, classes, distribution);
- Cohen kappa >= 0.75 on calibration slice, or a remediation plan is documented;
- issue contains class-imbalance report and hard-case list.

Commands:

- `make ml-export-action-seed ACTION_DB=app/data/db/birdlense.db ACTION_SEED_JSONL=/tmp/action_seed.jsonl ACTION_SEED_MANIFEST=/tmp/action_seed_manifest.json`
- `make ml-verify-action-agreement ACTION_ANN_A=/tmp/annotator_a.jsonl ACTION_ANN_B=/tmp/annotator_b.jsonl ACTION_MIN_KAPPA=0.75 ACTION_AGREEMENT_REPORT=/tmp/action_kappa.json`

### Phase E2 — model candidate benchmark (#379)

- evaluate at least 2 candidates (light temporal head + clip-model baseline);
- train/evaluate on identical splits;
- record quality/latency/VRAM trade-offs.

DoD E2:

- comparison table exists (F1, boundary delay p95, FP/hour, latency);
- one production candidate and one fallback are selected;
- issue #379 contains eval artifacts and benchmark script commit.

Command:

- `make ml-benchmark-action-candidates ACTION_GT=/tmp/action_gt.jsonl ACTION_PRED=/tmp/action_predictions.jsonl ACTION_BENCHMARK_REPORT=/tmp/action_benchmark_report.json`

### Phase E3 — hub integration shadow (#379)

- integrate inference path without blocking species pipeline;
- keep weak-label fallback when action model is unavailable;
- add observability for action events and failures.

DoD E3:

- hub smoke confirms no species-flow regression;
- action output appears in `video_action_events@v1`/API payload without crash loops;
- kill-switch and rollback steps are documented.

### Phase E4 — guarded rollout (#379)

- enable limited rollout (camera/domain slice);
- gather post-deploy metrics in two consecutive windows;
- decide expand vs rollback.

DoD E4:

- quality bar in this document is met in two independent windows;
- detector/classifier throughput is not degraded;
- issue #379 includes final go/no-go report.
