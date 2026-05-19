# Behavior v2.1 — Roadmap (post-labeling, post-night-fixes)

**Date:** 2026-05-19  
**Epic:** #450 · **Reliability:** #451 · **Data/schema:** #476 · **Rollout doc:** #460  
**Commits (night fixes):** `6a19a37e`, `8c7cb7f6`, `e50d6cee`, `55d8ef44`, `86519f86` (v2 train baseline)

---

## Current state

| Area | Status |
|------|--------|
| User labeling | **Done** (confirmed) |
| Night marathon | Found Canary / Monitor / Blind bugs — **fixes deployed** (`dev` @ `55d8ef44`) |
| v2 prod model | 44 tracklets (feeding=40, flying=4), holdout Macro-F1 **0.44**, canary discrepancy **~31%** |
| `engine: auto` | **Blocked** until discrepancy **<20%** for ≥48h on ≥30 clips |

---

## Phase A — Stabilization (#451) — before tuning

**Goal:** Confirm runtime fixes on daylight traffic.

1. Run 2–4h validation (`scripts/validation_daylight_start.sh` + `validation_daylight_analyze.py`).
2. Metrics:
   - `blind_suspected` ≈ 0 when `yolo_raw_boxes_total > 0`
   - New videos: `behavior_shadow_label` not NULL (Canary)
   - Monitor JSON: non-zero `sessions` / `yolo_frames_with_tracks`
3. Only then: BirdBox A/B (LOW_CONFIDENCE, short-track guards) per original #451 plan.

**Do not close #451** until daylight validation passes.

---

## Phase B — Dataset v2.1 (#476)

### B1. Extract (prod DB on VPS)

```bash
docker exec birdlense bash -lc 'bash /app/scripts/behavior_v2_1_pipeline.sh'
# or step 1 only:
docker exec birdlense bash -lc 'cd /app && PYTHONPATH=/app/scripts:/app \
  python3 scripts/ml_behavior_extract_prod_labeled.py \
  --db /app/data/db/birdlense.db \
  --out /app/data/datasets/behavior_v2_1/behavior_dataset_v2.1.json \
  --crops-dir /app/data/datasets/behavior_v2_1/crops \
  --repo-root /app --min-confidence 0.85 --min-label-count 3'
```

**Filters:** `active_learning_case.status=approved` **OR** `video.behavior_confidence ≥ 0.85`, crops with blur gate.

### B2. Class balance gate

| Label | Min for train | If below |
|-------|---------------|----------|
| feeding | ≥15 | OK expected |
| flying | **≥15** | `ml_behavior_augment.py` (train-time copies) + optional `ml_behavior_import_wetlandbirds.py` |

If `flying < 10` after extract → **stop train**, report in #476, add synthetic/WetlandBirds.

### B3. Manifest

- Output: `/app/data/datasets/behavior_v2_1/behavior_dataset_v2.1.json`
- Schema: `behavior_tracklet_manifest@v1`, splits: train/val/holdout (stratified)

Optional merge: `make ml-merge-behavior-manifests` if WetlandBirds supplement added.

---

## Phase C — Train & validate v2.1

```bash
MANIFEST=/app/data/datasets/behavior_v2_1/behavior_dataset_v2.1.json \
OUT_DIR=/app/data/datasets/behavior_v2_1/artifacts \
BACKBONE=x3d \
make ml-train-behavior-video ARGS="--augment-copies 4"

VIDEO_EXPORT=/app/data/datasets/behavior_v2_1/artifacts/behavior_video_export@*.json \
OUT_DIR=/app/processor/models/behavior_v2_1_openvino \
make ml-export-behavior-video-openvino
```

**Targets (realistic small-data):**

| Metric | Gate |
|--------|------|
| Holdout Macro-F1 | **≥ 0.60** (stretch 0.70 if flying≥15) |
| Holdout accuracy | ≥ 0.75 |
| Flying recall | **> 0** (not all predicted feeding) |
| Canary replay discrepancy | **< 20%** on ≥30 clips |

`make ml-behavior-canary-gate` — offline replay vs meta_v1.

---

## Phase D — Canary deploy v2.1 → auto (#460)

1. Patch: `video_openvino_path: models/behavior_v2_1_openvino`, `video_model_kind: video_v2.1`, keep `engine: canary`.
2. Run **24–48h** canary on prod; log `behavior canary discrepancy`.
3. **Promote to `engine: auto`** only if:
   - discrepancy **<15–20%** over 24h
   - ≥30 clips with shadow labels
   - no blind-gate regression (#451 green)
4. Rollback: `engine: canary` if discrepancy **>25%** / 24h.

---

## GitHub sync

- [#451](https://github.com/Gfermoto/BirdLense-Hub/issues/451) — comment + checklist: daylight blind validation
- [#476](https://github.com/Gfermoto/BirdLense-Hub/issues/476) — comment + v2.1 pipeline checklist

Both issues: **In Progress** on roadmap project.

---

## Immediate next actions (ordered)

1. **VPS:** run extract → print `label_counts` (user or `behavior_v2_1_pipeline.sh`).
2. If `flying ≥ 10`: train v2.1 + export + canary replay.
3. If `flying < 10`: WetlandBirds import / augment plan — comment on #476.
4. Parallel: 2h daylight validation for #451.
5. Update #451/#476 when train completes with metrics + artifact paths.
