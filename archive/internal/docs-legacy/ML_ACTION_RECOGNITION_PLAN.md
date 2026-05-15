# Action Recognition Plan (v1)

[Русский](./ML_ACTION_RECOGNITION_PLAN.ru.md)

Parent issue: [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392) · runtime execution: [#416](https://github.com/Gfermoto/BirdLense-Hub/issues/416)
Related: [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379)

## Label taxonomy v1

Behavior labels are model-oriented and training-driven (for example: `feeding`, `alert`, `idle`).
Legacy weak labels (`arrival`, `departure`, `possible_feeding`) are archived and removed from runtime APIs.

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
- labels must be visually grounded in clip evidence
- avoid pseudo/proxy-only labels without model-trainable visual cues

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
- if action model is unavailable, no weak-label fallback is emitted in runtime API
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
- archive legacy weak-label gate protocol and keep only model/runtime behavior flow.

DoD E0:

- legacy gate scripts/fixtures are removed from runtime path;
- docs and smoke flows reference only current model/runtime behavior path.

### Phase E1 — dataset bootstrap (#392 -> #379)

- collect a seed set of action segments following current protocol;
- run calibration with double annotation;
- capture inter-annotator agreement and disagreement queue.

DoD E1:

- seed manifest is published (volume, classes, distribution);
- Cohen kappa >= 0.75 on calibration slice, or a remediation plan is documented;
- issue contains class-imbalance report and hard-case list.

Commands:

- Legacy command set removed after migration completion.

### Phase E2 — model candidate benchmark (#379)

- evaluate at least 2 candidates (light temporal head + clip-model baseline);
- train/evaluate on identical splits;
- record quality/latency/VRAM trade-offs.

DoD E2:

- comparison table exists (F1, boundary delay p95, FP/hour, latency);
- one production candidate and one fallback are selected;
- issue #379 contains eval artifacts and benchmark script commit.

Command:

- Legacy command removed after migration completion.

### Phase E3 — hub integration shadow (#379)

- integrate inference path without blocking species pipeline;
- add observability for behavior model outputs and failures.

DoD E3:

- hub smoke confirms no species-flow regression;
- behavior output appears in `GET /api/ui/videos/:id` payload without crash loops;
- kill-switch and rollback steps are documented.

Command:

- Legacy command removed after migration completion.

### Phase E4 — guarded rollout (#379)

- enable limited rollout (camera/domain slice);
- gather post-deploy metrics in two consecutive windows;
- decide expand vs rollback.

DoD E4:

- quality bar in this document is met in two independent windows;
- detector/classifier throughput is not degraded;
- issue #379 includes final go/no-go report.

## Hub #416 — behavior baseline runtime (implemented)

Checklist aligned with issue [#416](https://github.com/Gfermoto/BirdLense-Hub/issues/416):

- **DB**: `video.behavior_label`, `video.behavior_confidence` (migration), ingest from processor finalize path.
- **Processor**: `behavior_logistic_export@v1.json` load, softmax inference, **cap** on detections passed into meta-features (default 50) to bound work per clip.
- **API**: `GET /api/ui/videos/:id` exposes `behavior_*`; `PATCH` allows contributor/admin to set or clear manual labels (OpenAPI + UI).
- **Scripts** (optional ops):
  - `scripts/ml_behavior_export_video_labels.py --db … --out ….jsonl` — dump operator-confirmed labels from SQLite for retraining feedback.
  - `scripts/ml_behavior_runtime_profile.py --export … --out ….json` — micro-benchmark forward pass latency (numpy softmax path).

Future waves (not required for #416 closure): OpenVINO/ONNX head, full operator loop → export, extended canary metrics.
