# Datasets & models — BirdLense Hub

Formats, scripts, sources, and training hardware. **End-to-end training:** [TRAINING](./TRAINING.md).

[Русский](./DATASETS.ru.md)

---

## 1. Models

| Component | Version | Trained on |
|-----------|---------|------------|
| **Detector** | YOLOv8n | NABirds + COCO birds + OIDv4 squirrel (binary bird/squirrel) |
| **EU classifier** | YOLO11n-cls | birds-525 + iNaturalist (~491 species) — active `best.pt` |
| **US classifier** | YOLOv8n-cls | NABirds (~400 species) — `best_US.pt` |

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
| `classification/weights/best.pt` | EU classifier (default) |
| `classification/weights/best_US.pt` | US backup |
| `detection/weights/best.pt` | Binary detector |

---

## 4. Public datasets

### EU (primary)

| Dataset | Species | Link |
|---------|---------|------|
| **34data/birds-525-species** | 525 | [Hugging Face](https://huggingface.co/datasets/34data/birds-525-species) |
| **iNaturalist Europe** | many | [API](https://api.inaturalist.org/v1/docs/), e.g. `place_id=96372` |

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
BirdLense recordings → (planned) export_birdlense_to_yolo.py → YOLO dataset
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
