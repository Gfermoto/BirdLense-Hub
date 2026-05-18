# How to run Fine-Tuning on collected data

This guide describes the shortest path from production hard cases to a new detector/classifier candidate.

## 1) Mine hard cases

Run miner from UI (`/labelling`, button **Run Hard-Case Miner**) or via API:

```bash
curl -X POST "http://localhost:8085/api/ui/labelling/cases/mine" \
  -H "Content-Type: application/json" \
  --cookie "session=..." \
  -d '{"lookback_hours":72,"max_rows":500}'
```

Selection criteria:

- `blind_score > experimental.active_learning_blind_score_threshold`
- `fallback_ratio > experimental.active_learning_fallback_ratio_threshold`
- `confidence in [experimental.active_learning_conf_min, experimental.active_learning_conf_max]`

## 2) Review and approve labels

Open `/labelling`:

- approve valid samples (`approved`)
- reject noise (`rejected`)
- keep uncertain samples as `pending`

MVP stores review state + metadata (`reason_code`, `camera_id`, timestamps).

## 3) Export dataset version

Use `/labelling` export button or API:

```bash
curl -X POST "http://localhost:8085/api/ui/labelling/export" \
  -H "Content-Type: application/json" \
  --cookie "session=..." \
  -d '{"format":"yolo","status":"approved"}'
```

Output:

- `app/data/datasets/vN/labels/*.txt` + `classes.txt` + `manifest.json` (YOLO), or
- `app/data/datasets/vN/annotations.coco.json` (COCO)

## 4) Create train/val/test and train

Recommended flow:

1. Merge approved `vN` with your baseline dataset snapshot.
2. Keep validation split fixed between experiments.
3. Train candidate weights in isolated experiment folder.

Example starter commands:

```bash
cd app
make ml-build-behavior-dataset
make ml-train-behavior-baseline
```

For detector/classifier-specific pipelines, use your existing training scripts in `scripts/datasets/*` and keep experiment metadata next to artifacts.

## 5) Evaluate and gate

Minimum gates before rollout:

- Recall gain on hard cases > baseline
- FPR does not regress beyond allowed delta
- Runtime latency budget preserved (processor p95)
- `make ci-local` green

For SR experiments, run:

```bash
python scripts/benchmark_sr_roi_pilot.py
```

## 6) Rollout plan

1. Deploy candidate in shadow or limited camera scope.
2. Monitor first 24h: blind score, fallback ratio, self-heal events.
3. If stable, switch to wider rollout.
4. Keep rollback-ready previous snapshot in `weights/snapshots/`.
