# Datasets & models — BirdLense Hub

Formats, scripts, sources, and training hardware. **End-to-end training:** [TRAINING](./TRAINING.md).

[Русский](./DATASETS.ru.md)

---

## Canonical paths (current repo)

Do not duplicate long command lists here — **`scripts/datasets/README.md`** is the command reference.

| What | Path / command |
|------|----------------|
| Detector inputs + **`make dataset-merge-three-class`** | `datasets/new/detector/binary/birds/`, `binary/rodent/`, `binary/background/` |
| **Default merge output** (Makefile) | `datasets/new/detector/yolo/` — `make dataset-merge-three-class` |
| Manual merge from `scripts/datasets/` | `python3 scripts/datasets/merge_datasets_three_class.py --birds-dir … --output-dir …` (any paths) |
| Legacy tree under `scripts/datasets/` | `scripts/datasets/binary/{birds,rodent,background}/`, optional `binary/merged/` |
| Optional **shipping** folder for Drive/Colab ZIP | `scripts/datasets/brg/` — same layout as `merged/`; fill by **copy/sync from `binary/merged/`** after enrichment/dedupe, **or** run `merge_datasets_three_class.py` with `--output-dir brg` (Makefile always targets `binary/merged/`) |
| Pack YOLO → zip | `python3 scripts/datasets/pack_brg_for_gdrive.py` → **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`** (default source: **`datasets/new/detector/yolo`**) |
| Disk layout detail | `scripts/datasets/DETECTOR_DATA_LAYOUT.md`, `scripts/datasets/binary/README.md` |
| Hugging Face detector zips | Different filenames (`detector_merged_*`, etc.) — [BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main); not the same as local `BirdLense_detector_brg_*.zip` |
| Classifier merged dirs (local) | Often repo-root `datasets/merged_cls/` etc. — gitignored; see [TRAINING](./TRAINING.md) |

---

## `datasets/new/` — dataset sources

Root **`datasets/new/`** is the primary local ETL area: detector, classifier, manifest helpers. Below: **data sources by subdirectory** (check licenses and filters at the original datasets).

### Named public datasets (COCO, CUB, Open Images, …)

Which **canonical benchmark corpus** feeds which Hub detector class or classifier layer (CLI details in scripts and **`scripts/datasets/DETECTOR_DATASET_QUALITY.md`**).

**Detector** (inputs under `binary/*`, then **`make dataset-merge-three-class`** → `yolo/`):

| Named dataset | Hub role (after merge) | How it is wired |
|---------------|------------------------|-----------------|
| **MS COCO 2017** | **Bird** (`bird` boxes), **Background** (no-bird frames + empty `.txt`) | **`bootstrap_detector_yolo.py`** (FiftyOne zoo `coco-2017`) |
| **Google Open Images V6** | **Bird** (optional **Bird** detections), **Rodent** (chosen species / `--rodent-classes`) | **`bootstrap_detector_yolo.py`** (`--birds-oid-*`, `--rodent-*`, validation-only, etc.) |
| **Caltech-UCSD Birds-200-2011** (**CUB-200-2011**) | **Bird** | **`convert_cub_to_yolo.py`** / **`make dataset-import-cub`** (`--root datasets/new/detector`, local unpacked tarball) |
| **Roboflow Universe — Bird-Feeder** (**YOLOv11** export, e.g. **dataset v3**) | **Bird** | **`import_roboflow_bird_feeder_birds.py`**; source ZIP often under **`detector/raw/`** |
| **Open Images** (**OIDv4 Toolkit** folder export) | **Rodent** | **`convert_oidv4_rodent_to_yolo.py`** → `binary/rodent/` |
| **Operator / Hub camera frames** | **Background** | **`import_hub_background_folder.py`** |
| Extra **hard-negative** mines (often **OID**: person / dog / cat, …) | usually **Background** | Policy in **`DETECTOR_DATASET_QUALITY.md`** + **`bootstrap_detector_yolo.py`** |
| **NABirds** | separate species-hierarchy line | **`convert_nabirds_to_yolo*.py`** — **not** required for the standard three-class merge |

**Classifier** (species, under `datasets/new/classifier/`):

| Named corpus | Notes |
|--------------|-------|
| **`gfermoto/birds-eu-merged`** (HF) | Base EU layer — **`download_birds_eu_merged.py`** |
| **iNaturalist** (research-grade, regional filters) | **`download_inaturalist.py`**, rare-class backfill — **`backfill_classifier_open.py`** |
| **birds-525** (HF mirrors) | **`download_hf_birds.py`** (`--format scientific_common`) |
| **BirdLense Hub** labeling export | **`export_birdlense_to_yolo.py`** |
| **CUB-200-2011**, BirdCLEF / LifeCLEF, Macaulay Library, NABirds, GBIF, … | Mostly manual / separate pipelines — see **`EU_CLASSIFIER.md`** |

### Detector — `datasets/new/detector/`

| Path | Role | Data sources |
|------|------|----------------|
| **`binary/birds/`** | Merge input, Bird class | **COCO 2017** (`bird` class) via **`bootstrap_detector_yolo.py`** (FiftyOne); **Roboflow Universe — Bird-Feeder [YOLOv11, dataset v3](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11)** via **`import_roboflow_bird_feeder_birds.py`** (`--root datasets/new/detector`, all species labels → single bird class); export ZIP may live under **`raw/`** (e.g. `Bird-Feeder.v3i.yolov11.zip`); optionally **CUB-200-2011** (`make dataset-import-cub`), other Roboflow ZIPs if license-compatible |
| **`binary/rodent/`** | Merge input, Rodent class | **Open Images V6** (boxable classes only; configure via **`--rodent-classes`** — there is **no** standalone **Rat** in OID boxable) via **`bootstrap_detector_yolo.py`**; optional **OIDv4 Toolkit** → **`convert_oidv4_rodent_to_yolo.py`**; optional **COCO instances** (camera traps / LILA) → **`import_coco_rodents_to_binary.py`** |
| **`binary/background/`** | Merge input, Background class | **COCO** scenes without bird + **empty** YOLO labels (bootstrap); operator / camera frames → **`import_hub_background_folder.py`** |
| **`yolo/`** | Output of **`make dataset-merge-three-class`** | Merged YOLO detect **Bird / Rodent / Background**: `train|val|test/{images,labels}` + **`dataset.yaml`** |
| **`raw/`** | Downloaded archives | ZIP exports (Roboflow, etc.) before import into `binary/` |
| **`manifests/`**, **`qa/`** | Build bookkeeping / QA | JSON manifests and check artifacts (**`datasets/new/tools/build_manifests.py`**) |

More commands: **`scripts/datasets/README.md`**; quality notes: **`scripts/datasets/DETECTOR_DATASET_QUALITY.md`**; **`binary/`** layout: **`datasets/new/detector/README_binary_layout.md`**.

### Exemplary Bird / Rodent detector for YOLOv11 (quality policy)

Goal: **YOLOv11 detection** training for merged classes **Bird** and **Rodent** (plus **Background** when building the full three-class set), using standard **multi-domain** practice to reduce domain shift.

**Hard rule.** `binary/birds/` and `binary/rodent/` must contain **only** image/label pairs whose boxes are **faithful to a primary detection dataset**: each training image has a real YOLO label file derived from that dataset’s annotations (COCO, Open Images, CUB `bounding_boxes.txt`, Roboflow YOLO exports, COCO-format camera-trap / LILA instances, etc.).

**Out of scope for an “exemplary” pipeline:** folders of unlabeled photos; synthetic single full-frame boxes **without** upstream boxes; mixing taxa (e.g. shrews into Rodent) without an explicit product decision.

**Bird mix (evidence-based layering):** (1) **COCO 2017** `bird` — broad baseline; (2) **Open Images Bird** — extra clutter / web domain; (3) **Roboflow YOLOv11** (e.g. Bird-Feeder) — feeder-like domain with native YOLO boxes; (4) **CUB-200-2011** — fine-grained poses; cap its share vs COCO/OID if your deployment is field cameras.

**Rodents:** **Open Images V6** with **boxable** `--rodent-classes` only; scale with **COCO instances** importers (e.g. `import_coco_rodents_to_binary.py`) or **OIDv4 Toolkit** via `convert_oidv4_rodent_to_yolo.py`.

**Post-merge** (`make dataset-merge-three-class` → `datasets/new/detector/yolo/`): **`make dataset-dedupe-detector-yolo`** (default stays **within** `b_`/`r_`/`g_` prefixes), **`make dataset-validate-yolo-labels`**, then optional profile + **`make dataset-verify-quality-gates`**.

### Classifier — `datasets/new/classifier/`

| Path / artifact | Data source |
|-----------------|-------------|
| **`yolo_cls_eu_hf/`** | Hugging Face **[`gfermoto/birds-eu-merged`](https://huggingface.co/datasets/gfermoto/birds-eu-merged)** — **`download_birds_eu_merged.py`** |
| **`raw/inat_europe_bulk/`** | **iNaturalist**: Europe (default `place_id`), **Aves**, research-grade — **`download_inaturalist.py`** |
| **`raw/source_birds525/`** | **birds-525** layer (HF mirrors) — **`download_hf_birds.py`** and related scripts |
| **`raw/source_inaturalist/`** | iNaturalist pulls for specific tasks |
| **`yolo_cls/`** | Working YOLO-cls layout after merge / edits |
| **`yolo_cls_eu_merged/`** | Output of **`merge_classification_datasets.py`** from multiple `--inputs` |
| **`yolo_cls_caps_legacy/`** | Legacy CAPS-name layout |
| **`manifests/`**, **`qa/`**, **`reports/`** | Build manifests, QA, class reports |

Full EU pipeline and optional external sources: **`scripts/datasets/EU_CLASSIFIER.md`**.

### Tools — `datasets/new/tools/`

**`build_manifests.py`** generates manifests for detector and classifier; see **`datasets/new/tools/README.md`**.

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

Reproducible **YOLO detection** layout with classes **Bird**, **Rodent**, **Background** (aligned with `normalize_detector_label` in `app/processor/src/detector_labels.py`). **`make dataset-merge-three-class`** reads **`datasets/new/detector/binary/{birds,rodent,background}/`** by default and writes **`datasets/new/detector/yolo/`**. Alternatively use **`scripts/datasets/binary/`** when invoking merge manually (see **`scripts/datasets/README.md`**).

- **Entrypoint:** `make dataset-merge-three-class` from the repo root, or  
  `python3 scripts/datasets/merge_datasets_three_class.py --help`
- **Output (default Makefile):** **`datasets/new/detector/yolo/dataset.yaml`** + merged `train`/`val`/`test`. Use **`scripts/datasets/brg/`** only as the folder you pack for Drive (see **Canonical paths** above).
- **Published artifacts (zip):** [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main)  
  (`detector_merged_balanced_20260429.zip`, `detector_merged_full_20260429.zip`).
- **Train/val policy:** follow Ultralytics defaults unless you fix a seed; treat **minimum images per class** as a training constraint — enforce via Hub export (`min_images_per_class`) or document your floor before shipping weights.
- **Hard negatives manifest** (optional bookkeeping for curated mines): JSON Schema `scripts/datasets/schemas/hard_negatives_manifest_v1.schema.json`, example `scripts/datasets/example_hard_negatives_manifest.json`. Pass `--manifest-out path.json` on merge to record paths and counts.
- **Quality gates (#394):** export profile + verify gates before training:
  `python3 scripts/datasets/export_detector_dataset_profile.py --dataset-root datasets/new/detector --out /tmp/detector_profile.json`
  then `make dataset-verify-quality-gates PROFILE=/tmp/detector_profile.json`.
- **Hard-negatives integrity gate (#394):**
  `make dataset-verify-hard-negatives MANIFEST=/path/to/hard_negatives_manifest.json`
  (optional strict mode: `DATASET_ROOT=scripts/datasets REQUIRE_EXISTING_FILES=1`).

Recommended detector training flow for these artifacts:
- **Stage A (stability):** train on `merged_balanced`
- **Stage B (diversity):** fine-tune from Stage A checkpoint on `merged` (full)

Phase 2 items from the epic (MineUp, dual mining, COCO export) remain future work; track under [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) / [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368).

### `brg` dataset and Drive ZIP — provenance and enrichment

**Starter weights for Colab fine-tuning:** put **`bl_best.pt`** on Drive — your current **YOLO11n detection** checkpoint from the Hub (or a copy from `app/processor/models/detection/weights/`). Fine-tune from that file per [ML_DETECTOR_COLAB.md](./ML_DETECTOR_COLAB.md) (two-stage `freeze` train, then OpenVINO export). Alternative “from scratch” on the same architecture: **`YOLO("yolo11n.pt")`** from Ultralytics (auto-download), no extra weights file on Drive.

**Where birds and rodents (`Rodent`, including mice) come from in `brg`:**

- **Bird:** two streams: (1) **COCO 2017** bird class via **`bootstrap_detector_yolo.py`** (FiftyOne); (2) Roboflow **YOLOv11** exports imported with **`import_roboflow_bird_feeder_birds.py`** (all label classes collapsed to a single bird class). Typical feeder enrichment uses **[Bird-Feeder on Universe](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11)** (dataset **v3** YOLOv11 export; older builds used v6 — **CC BY 4.0** in export metadata). The same importer works for other Roboflow bird datasets after you verify the project license; example public set: **[birds-yolo](https://universe.roboflow.com/birds-detection-2fyqw/birds-yolo)**.

- **Rodent:** **not** from Roboflow in this pipeline. Rodent boxes come from **Open Images V6** via FiftyOne + **`bootstrap_detector_yolo.py`** (**boxable** `--rodent-classes`; no separate **Rat** in OID boxable). Add **COCO-format** exports (e.g. LILA camera traps) with **`import_coco_rodents_to_binary.py`**, or **OIDv4 Toolkit** via **`convert_oidv4_rodent_to_yolo.py`** — see **`scripts/datasets/README.md`**. **Do not** train on unlabeled image dumps or synthetic full-frame pseudo-labels if you want an exemplary detector set.

- **Background:** COCO scenes without bird + empty labels (bootstrap), plus operator frames via **`import_hub_background_folder.py`** (step 4 below).

**Pipeline steps for the merged `brg` split (Bird / Rodent / Background):**

| Step | Source / action |
|------|-----------------|
| 1 | Local **`datasets/new/detector/binary/`** (or **`scripts/datasets/binary/`** if you keep a separate tree): birds from **COCO 2017** (bird class), rodents from **Open Images V6** (e.g. Squirrel/Mouse/Rat/Hamster), background — COCO frames **without** bird and empty YOLO labels. Fill via **`bootstrap_detector_yolo.py`** (`--root datasets/new/detector`, FiftyOne). |
| 2 | Merge to three Hub classes: **`merge_datasets_three_class.py`**. With **`make dataset-merge-three-class`** → **`datasets/new/detector/yolo/`**. For a Drive-ready tree named **`brg/`**, copy/sync after later steps or pass **`--output-dir brg`** when invoking the script manually. |
| 3 | **Bird feeder domain:** Roboflow **YOLOv11** export (Bird-Feeder project on Universe; export metadata — **CC BY 4.0**). Import into `binary/birds`: **`import_roboflow_bird_feeder_birds.py`** collapses all species labels to a **single bird** class (id 0). Keep the source ZIP under **`datasets/new/detector/raw/`** when helpful. Example export: [Bird-Feeder YOLOv11 download](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11); **`make dataset-import-roboflow-bird-feeder ROBOFLOW_ZIP=…`**. |
| 4 | **Real-domain background:** frames from an operator folder (e.g. **`scripts/datasets/detector/Background`**) via **`import_hub_background_folder.py`** into `binary/background` (empty `.txt` labels). |
| 5 | **Dedup** near-duplicate images (SHA256 per split): **`dedupe_yolo_images.py`**. |
| 6 | **Drive packaging:** **`pack_brg_for_gdrive.py`** → **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`**. |

Colab flow for this ZIP + **`bl_best.pt`**: [ML_DETECTOR_COLAB.md](./ML_DETECTOR_COLAB.md). Scripts: **`scripts/datasets/README.md`**.

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
| **Detector** | YOLO11n | Shipped lineage often described as NABirds + COCO birds + OID rodent/squirrel; hub maps rodent-like boxes to **Rodent**. **New rebuilds:** three-class **Bird / Rodent / Background** — same section as epic [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) above, not this table row alone. |
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

Full list and detector workflow: **`scripts/datasets/README.md`**. Below — quick index only.

### EU classifier (birds-525 + iNaturalist)

| Script | Role |
|--------|------|
| `export_birdlense_to_yolo.py` | BirdLense local crops (`app/data/dataset/train`) → YOLO cls `train/val` |
| `download_hf_birds.py` | Hugging Face → YOLO cls (`--format scientific_common`) |
| `download_inaturalist.py` | iNaturalist Europe → YOLO cls |
| `merge_classification_datasets.py` | Merge splits |
| `download_and_merge_all.sh` | Full pipeline → `merged_cls` |

### Detector — older / auxiliary scripts

Still useful for some sources; **primary three-class path** is `bootstrap_detector_yolo.py` + imports + **`merge_datasets_three_class.py`** (see README).

| Script | Role |
|--------|------|
| `convert_nabirds_to_yolo.py` | NABirds → YOLO |
| `download_coco_birds.py` | COCO birds for binary |
| `merge_datasets_binary.py` | NABirds + COCO → single “bird” class (input to older flows) |

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

The shipped detector is commonly described as trained on **NABirds + COCO birds + OIDv4 squirrel** (Open Images naming); the hub normalizes rodent-like heads to **Rodent**. That narrative may pre-date the **Bird / Rodent / Background** rebuild recipe (§ epic #367 above). The shipped EU classifier is trained on **birds-525 + iNaturalist Europe (~490/491 species)**.

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
| **Hugging Face (detector)** | [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) — 3-class detector zips (balanced + full) |
| **Zenodo** | DOI snapshots for papers |

---

## See also

[TRAINING](./TRAINING.md) · [FEATURES](./FEATURES.md) · [CONFIGURATION](./CONFIGURATION.md)
