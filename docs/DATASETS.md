# Datasets & models — BirdLense Hub

Formats, scripts, sources, and training hardware. **End-to-end training:** [TRAINING](./TRAINING.md).

[Русский](./DATASETS.ru.md)

---

## CV / ML prep gate (#377)

Before starting the CV / ML roadmap epic, keep the detector/classifier contract
in [CV_ML_PREP](./CV_ML_PREP.md) in sync with this page. In short: first-stage
detector boxes enter the species classifier only if their normalized label is in
`processor.detector_scope` (default `["Bird", "Rodent"]`). Background /
hard-negative detector classes are detector-only evidence and must stay outside
that scope.

---

## Three-class detector dataset — epic [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) Phase 1

Reproducible **YOLO detection** layout with classes **Bird**, **Rodent**, **Background** (aligned with `normalize_detector_label` in `app/processor/src/detector_labels.py`). Prerequisite folders under `scripts/datasets/binary/` — **`birds/`**, **`rodent/`**, **`background/`** (after `merge_datasets_binary.py`, `convert_oidv4_rodent_to_yolo.py`, and your curated background split with `train|val/images` and optional `labels/`):

- **Entrypoint:** `make dataset-merge-three-class` from the repo root, or  
  `python3 scripts/datasets/merge_datasets_three_class.py --help`
- **Output:** `scripts/datasets/binary/merged/dataset.yaml` + merged `train`/`val`/`test` splits.
- **Train/val policy:** follow Ultralytics defaults unless you fix a seed; treat **minimum images per class** as a training constraint — enforce via Hub export (`min_images_per_class`) or document your floor before shipping weights.
- **Hard negatives manifest** (optional bookkeeping for curated mines): JSON Schema `scripts/datasets/schemas/hard_negatives_manifest_v1.schema.json`, example `scripts/datasets/example_hard_negatives_manifest.json`. Pass `--manifest-out path.json` on merge to record paths and counts.

Phase 2 items from the epic (MineUp, dual mining, COCO export) remain future work; track under [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) / [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368).

---

## Library operational flow (Hub)

Critical daily operator happy-path in `Library`:

1. **Import from disk** (`Scan and import`).
2. **Regenerate** for the period (`Spectrograms` -> `Tracks`).
3. **Export dataset ZIP** (optional: `only manually corrected`).
4. **Maintenance**: use `retro-export` for backfill and `clean dataset` for cleanup.

### The “All time” range

`Library` now includes an **“All time”** preset. It does not guess from the calendar; it derives the range from recordings actually present on disk (`storage/stats`), so it can safely target the whole archive without manual date hunting.

Practical guidance:
- start with the **last 7 or 30 days** if you want to estimate runtime first;
- use **“All time”** when the device is idle and not busy with live capture;
- on very large archives, **track regeneration** is usually the heaviest operation, then **spectrogram regeneration**; dataset ZIP export is usually lighter when crops already exist.

`System` metric "Unique visitors" is defined as the number of `SpeciesVisit` sessions in the selected period (visit sessions, not unique individual birds).

### Train-ready export

In `Library -> Export dataset`, enable **"Train-ready (auto train/val split, no post-script)"**.  
Optionally enable **"Add test split (~10%)"** to include `test/<class>/...` (hold-out).
For the official BirdLense retraining loop, use:

- `ready_for_train=1`
- `strict_quality=1`
- `only_manually_corrected=1` when you need the cleanest corrective set
- `dataset_info.json` + `classes.txt` as mandatory rollout evidence artifacts

The ZIP will include:
- `train/<class>/...`, `val/<class>/...`, and optionally `test/<class>/...`
- `classes.txt`
- `dataset_info.json` — export passport (`manifest.schema=birdlense_dataset_export_v2`, filters, `split_seed`, `fingerprint_sha256_16`) and a **`quality`** block: duplicate `(video_id, track_id)` rows and cross-split `video_id` leakage.

API: `GET /api/ui/dataset/export` supports `test_ratio` and `strict_quality=1` (abort on duplicate tracks, cross-split video leakage, or — with **ready_for_train** — any class below `min_images_per_class`).

Before rolling out new weights, validate the export + artifacts together:

```bash
make validate-weights DATASET_INFO=/path/to/dataset_info.json CLASS_NAMES=/path/to/classes.txt
```

This removes the mandatory intermediate `scripts/datasets/export_birdlense_to_yolo.py` step for the basic finetuning path.

---

## 1. Models

| Component | Version | Trained on |
|-----------|---------|------------|
| **Detector** | YOLO11n | NABirds + COCO birds + OIDv4 squirrel (training data; runtime binary is **bird / rodent** → hub label **Rodent**) |
| **EU classifier** | YOLO11n-cls | birds-525 + iNaturalist (~491 species) — active `best.pt` |
| **US classifier** | YOLO11n-cls | NABirds (~400 species) — `best_US.pt` |

Switch to US: `cp best_US.pt best.pt`.

---

## 2. Name format: `Scientific (Common)`

Shared convention for merge, Frigate, BirdNET, YOLO:

| Source | Raw | Normalized |
|--------|-----|--------------|
| **Frigate** | `Cardinalis cardinalis (Northern Cardinal)` | as-is |
| **iNaturalist** | `Columba palumbus` | `Columba palumbus (Common Wood Pigeon)` |
| **birds-525** | `GOLDEN_EAGLE` | `Aquila chrysaetos (Golden Eagle)` |

**YOLO cls folders:** `train/Parus major (Great Tit)/img.jpg`, same class names under `val/`.

---

## 3. Scripts (`scripts/datasets/`)

### EU classifier (birds-525 + iNaturalist)

| Script | Role |
|--------|------|
| `export_birdlense_to_yolo.py` | BirdLense local crops (`app/data/dataset/train`) → YOLO cls `train/val` |
| `download_hf_birds.py` | Hugging Face → YOLO cls (`--format scientific_common`) |
| `download_inaturalist.py` | iNaturalist Europe → YOLO cls |
| `merge_classification_datasets.py` | Merge splits |
| `download_and_merge_all.sh` | Full pipeline → `merged_cls` |

### Detector (legacy)

| Script | Role |
|--------|------|
| `convert_nabirds_to_yolo.py` | NABirds → YOLO |
| `download_coco_birds.py` | COCO birds for binary |
| `merge_datasets_binary.py` | NABirds + COCO → binary |

### Weights (`app/processor/models/`)

| Path | Role |
|------|------|
| `classification/weights/best.pt` | EU classifier from [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) (YOLO11n-cls, default) |
| `classification/weights/best_US.pt` | US backup (optional) |
| `classification/weights/class_names.txt` | Class allowlist for catalog alignment |
| `detection/weights/best.pt` | Binary detector (YOLO11n); zip from [AleksandrRogachev94/BirdLense `app/processor`](https://github.com/AleksandrRogachev94/BirdLense/tree/main/app/processor) |

Everything else in `app/processor/models/` is training/export output, not runtime input.

---

## 4. Public datasets

### EU (primary)

| Dataset | Species | Link |
|---------|---------|------|
| **34data/birds-525-species** | 525 | [Hugging Face](https://huggingface.co/datasets/34data/birds-525-species) |
| **iNaturalist Europe** | many | [API](https://api.inaturalist.org/v1/docs/), e.g. `place_id=96372` |

The shipped detector is trained on **NABirds + COCO birds + OIDv4 squirrel** (Open Images rodent class name in the dataset); the hub normalizes the binary head to **Rodent**. The shipped EU classifier is trained on **birds-525 + iNaturalist Europe (~490/491 species)**.

### North America (weak signal for EU accuracy)

| Dataset | Species |
|---------|---------|
| NABirds | ~400 |
| [sasha/birdsnap](https://huggingface.co/datasets/sasha/birdsnap) | 500 |
| [randall-lab/cub200](https://huggingface.co/datasets/randall-lab/cub200) | 200 |

---

## 5. Hardware for training

| Platform | GPU | Cost |
|----------|-----|------|
| **Google Colab** | T4 (15 GB) | Free tier |
| **RunPod** | RTX 4090, A100 | ~$0.40–0.80/h |
| **Local** | Your GPU | — |

**Practical default:** Colab Free (T4) — see [TRAINING](./TRAINING.md).

---

## 6. Pipeline: collect → train

```
BirdLense recordings → export_birdlense_to_yolo.py → YOLO dataset
                                        ↓
birds-525 + iNaturalist → merge_classification_datasets.py → merged_cls
                                              ↓
                              TRAINING.md (Colab) → best.pt
```

---

## 7. Publishing artifacts

| Platform | Use |
|----------|-----|
| **Hugging Face** | [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged), [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) — see [TRAINING](./TRAINING.md) |
| **Zenodo** | DOI snapshots for papers |

---

## See also

[TRAINING](./TRAINING.md) · [FEATURES](./FEATURES.md) · [CONFIGURATION](./CONFIGURATION.md)
