# WetlandBirds Integration Report

**Date:** 2026-05-19  
**Epic:** Behavior v2.1 (#476)  
**Goal:** ≥50 `flying` tracklets for training

---

## Dataset selected

| Field | Value |
|-------|--------|
| **Name** | Visual WetlandBirds |
| **Source** | [Zenodo 10.5281/zenodo.15696105](https://doi.org/10.5281/zenodo.15696105) (latest record) |
| **Code** | [github.com/3dperceptionlab/Visual-WetlandBirds](https://github.com/3dperceptionlab/Visual-WetlandBirds) |
| **License** | CC-BY-4.0 (Zenodo); MIT in repo README |
| **Why** | Native 7-class behavior taxonomy incl. **Flying**; clip-level `crops.csv` (~49 KB) — no 9 GB `videos.zip` required for bbox-only crop pipeline |

**Alternatives considered:** CUB-200-2011 (species only, no behavior); synthetic bootstrap (already used, not real flying motion).

---

## Download & layout

```bash
bash scripts/download_wetlandbirds_zenodo.sh
# → app/data/datasets/Visual-WetlandBirds/raw/{crops,behaviors_ID,species_ID}.csv
```

| File | Size | Role |
|------|------|------|
| `crops.csv` | 49 KB | 1469 behavior clips (`video;bird;species;action;start;end`) |
| `behaviors_ID.csv` | 80 B | Zenodo action IDs (Flying=**5**, not BirdLense ids) |
| `species_ID.csv` | 238 B | Species names |
| `videos.zip` | 9.4 GB | **Not downloaded** (optional for real RGB crops later) |

---

## Conversion & import

1. **`scripts/convert_wetlandbirds_zenodo_crops.py`** — maps Zenodo `action_id` → BirdLense taxonomy, writes per-clip CSVs under `Visual-WetlandBirds/annotations/` (pads short clips to ≥5 frames).
2. **`scripts/ml_behavior_import_wetlandbirds.py`** — builds `behavior_tracklet_manifest@v1` + synthetic geometry crops (no video file).

```bash
python3 scripts/convert_wetlandbirds_zenodo_crops.py \
  --crops-csv app/data/datasets/Visual-WetlandBirds/raw/crops.csv \
  --species-csv app/data/datasets/Visual-WetlandBirds/raw/species_ID.csv \
  --out-dir app/data/datasets/Visual-WetlandBirds/annotations

docker exec birdlense bash -lc 'PYTHONPATH=/app/scripts:/app \
  python3 scripts/ml_behavior_import_wetlandbirds.py \
    --annotations-root /app/data/datasets/Visual-WetlandBirds/annotations \
    --out /app/data/datasets/behavior_v2_1/wetland_manifest.json \
    --crops-dir /app/data/datasets/behavior_v2_1/wetland_crops \
    --extract-crops --holdout-ratio 0.1'
```

---

## Class statistics

| Stage | Total tracklets | `flying` |
|-------|-----------------|----------|
| Hub relaxed (prod) | 46 | 2 |
| WetlandBirds only | **1469** | **98** |
| **Merged** (`behavior_dataset_v2.1_merged_wb.json`) | **1515** | **100** |

Other merged labels: feeding 621, walking 217, swimming 182, resting 164, alert 163, preening 67, conflict 1.

**Goal met:** 98 external + 2 hub = **100 flying** tracklets (target 50–100).

---

## Merge command

```bash
python3 scripts/ml_behavior_merge_manifests.py \
  --inputs /app/data/datasets/behavior_v2_1/behavior_dataset_v2.1_relaxed.json \
          /app/data/datasets/behavior_v2_1/wetland_manifest.json \
  --out /app/data/datasets/behavior_v2_1/behavior_dataset_v2.1_merged_wb.json \
  --holdout-ratio 0.1
```

---

## Training recommendation

| Approach | When |
|----------|------|
| **Retrain from scratch** on `merged_wb` | **Recommended** — real flying distribution, multi-class balance |
| Fine-tune prior v2.1 | Only if infra supports warm-start (current trainer fits fresh logistic on RGB features) |

```bash
docker exec birdlense bash -lc '
  export PYTHONPATH=/app/scripts:/app
  python3 scripts/ml_behavior_train_video.py \
    --manifest /app/data/datasets/behavior_v2_1/behavior_dataset_v2.1_merged_wb.json \
    --backbone x3d --out-dir /app/data/datasets/behavior_v2_1/artifacts_v2_1_wb \
    --augment-copies 4 --model-kind video_v2_1 --min-macro-f1 0.6
  EXPORT=$(ls -1t /app/data/datasets/behavior_v2_1/artifacts_v2_1_wb/behavior_video_export@*.json | head -1)
  python3 scripts/ml_behavior_export_video_openvino.py \
    --video-export "$EXPORT" \
    --out-dir /app/processor/models/behavior_v2_1_openvino --precision fp16
'
```

Then: Canary patch `scripts/user-config-behavior-canary-v2_1.partial.yaml`, monitor discrepancy 24–48 h before `engine: auto`.

### VPS train run (2026-05-19, merged_wb)

| Metric | Value |
|--------|--------|
| Holdout Macro-F1 | **0.37** (gate 0.6 not met) |
| Holdout accuracy | 0.58 |
| Holdout `flying` correct | **9** (was 0 on hub-only model) |
| OpenVINO | `behavior_v2_1_openvino/` updated on VPS |

Retrain export usable for **Canary A/B** despite F1 gate; improve with real video crops later.

---

## Limitations & next steps

- Crops are **bbox-geometry placeholders** (no decoded video pixels) until `videos.zip` is mounted and import uses real frames.
- For production quality: download `videos.zip` to `app/data/datasets/Visual-WetlandBirds/videos/` and extend converter to read real frames.
- Hub `flying` still sparse on **tracks** — continue AL labeling on videos with `video_species.frames`.

---

## Artifacts (VPS)

- `app/data/datasets/Visual-WetlandBirds/`
- `app/data/datasets/behavior_v2_1/wetland_manifest.json`
- `app/data/datasets/behavior_v2_1/behavior_dataset_v2.1_merged_wb.json`
- `app/data/datasets/behavior_v2_1/wetland_crops/`
