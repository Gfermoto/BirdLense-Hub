# Dataset Scripts

Scripts for preparing bird detection training datasets. Uses [NABirds](https://dl.allaboutbirds.org/nabirds) as the base dataset.

## EU classifier (приоритет: максимум европейских видов)

Пайплайн **без вырезания классов** для баланса — см. **[EU_CLASSIFIER.md](./EU_CLASSIFIER.md)**.

- **download_birds_eu_merged.py** — скачать [`gfermoto/birds-eu-merged`](https://huggingface.co/datasets/gfermoto/birds-eu-merged) (~490 видов, Scientific (Common))
- **build_eu_classifier_yolo.sh** — скелет сборки (HF + опционально iNat + merge + refine)

Дополнительный объём: увеличивайте `--max-obs` в **download_inaturalist.py** и мержите вторым входом в **merge_classification_datasets.py**.

## EU birds: birds-525 + iNaturalist (формат Scientific (Common))

- **download_hf_birds.py** — Hugging Face (birds-525) → YOLO cls, `--format scientific_common`
- **download_inaturalist.py** — iNaturalist Europe API → YOLO cls
- **export_birdlense_to_yolo.py** — BirdLense `app/data/dataset/train` → YOLO cls `train/val` split
- **species_format.py** — утилиты: format, parse, маппинг inat_bird_labels
- **merge_classification_datasets.py** — объединить датасеты
- **refine_classifier_yolo_cls.py** — дедуп между сплитами, опционально нормализация имён папок, выделение `test/`, глобальный дедуп (`--dedupe-global-only`, при необходимости `--skip-rebalance`)
- **balance_classifier_yolo_cls.py** — финальная выборка под обучение: отсечь классы с `< min-images`, ограничить верх до `max-ratio × min` класса, перераспределить **train/val/test** (по умолчанию 70/20/10)
- **download_and_merge_all.sh** — полный пайплайн
- **dump_classifier_allowlist.py** — имена классов из `best.pt` → `class_names.txt` для `species.catalog_allowlist_file` в Hub ([CONFIGURATION](../../docs/CONFIGURATION.md))
- **../validate-processor-weights.py** — финальная проверка rollout-кандидата (`best.pt` + `class_names.txt` + `dataset_info.json`)

Формат имён: `Scientific_name (Common Name)` — совпадает с Frigate. См. [docs/DATASETS.md](../docs/DATASETS.md).

## Детектор (Bird / Rodent / Background)

Сборка данных: **`bootstrap_detector_yolo.py`** → **`make dataset-merge-three-class`** → `binary/merged/`.

Усиление качества (второй домен птиц OID **Bird**, hard-negative фон person/dog/cat): **[DETECTOR_DATASET_QUALITY.md](./DETECTOR_DATASET_QUALITY.md)**.

Быстрый большой прогон: **`build_detector_dataset_large.sh`** (числа править внутри).

## convert_nabirds_to_yolo.py

Converts raw NABirds dataset to [Ultralytics YOLO format](https://docs.ultralytics.com/datasets/) used for training.

## remove_unused_classes.py

Removes all classes that don't have actual images from the converted dataset. Needed because NABirds uses a hierarchical class structure where only the leaf nodes have images. Improves model performance and reduces computation.

## convert_nabirds_to_yolo_reduced.py

Similar to `convert_nabirds_to_yolo.py`, but groups gender-specific classes into single classes based on the hierarchy. Results in fewer classes for simpler training. Performance improvement was marginal (~2% mAP50-95), so this dataset is not actively used.

## build_name_hierarchy.py

Converts NABirds' `hierarchy.txt` from `child_id:parent_id` format to `child_name:parent_name` format. The result is used in BirdLense Hub for species categorization.

## convert_oidv4_rodent_to_yolo.py

Converts OIDv4 dataset (Open Images **/m/071qp** — upstream export folders `train/Squirrel`, `validation/Squirrel` from [OIDv4 Toolkit](https://github.com/EscVM/OIDv4_ToolKit)) to YOLO layout under **`binary/rodent/`** with `dataset.yaml` class name **Rodent** (index `1011` unchanged for compatibility with existing NABirds merge recipes). Исторически скрипт назывался `convert_oidv4_squirrel_to_yolo.py`, выход — `squirrel_yolo/`; актуальный путь по умолчанию — **`binary/rodent/`**.

## download_coco_birds.py

Downloads COCO 2017 dataset filtered to only include images containing birds. Uses `fiftyone` library for efficient download and filtering, then converts to YOLO format.

Requires: `pip install fiftyone pycocotools`

## merge_datasets_binary.py

Merges the cleaned NABirds dataset (`nabirds_yolo_cleaned/`) with COCO birds (`coco_birds_yolo/`) and collapses all species into a single "bird" class (class 0). Creates a binary detection dataset for training a general bird detector without species classification.

## merge_datasets_three_class.py ([epic #367](https://github.com/Gfermoto/BirdLense-Hub/issues/367))

Merges **`binary/birds/`** + **`binary/rodent/`** + **`binary/background/`** into **`binary/merged/`** with YOLO class ids **0 = Bird**, **1 = Rodent**, **2 = Background** and `dataset.yaml` names matching the Hub (`Bird` / `Rodent` / `Background`). Background images may use **empty** label files (image-level negatives).

From repo root: **`make dataset-merge-three-class`** (expects those folders under `scripts/datasets/`). Options: `--manifest-out` for a merge audit JSON; see [DATASETS.md](../docs/DATASETS.md). Hard-negative manifest schema: `schemas/hard_negatives_manifest_v1.schema.json`.

## bootstrap_detector_yolo.py

Creates **`binary/birds`**, **`binary/rodent`**, **`binary/background`** and downloads **starter** subsets via **FiftyOne**: COCO 2017 (`bird`), Open Images V6 (`Squirrel`), COCO scenes **without** `bird` for background (empty labels). Large blobs are gitignored — see [DETECTOR_DATA_LAYOUT.md](./DETECTOR_DATA_LAYOUT.md) and [binary/README.md](./binary/README.md).

Requires: `pip install fiftyone pyyaml`

From repo root: **`make bootstrap-detector-data`** (optional: `ARGS='--birds-train 80 …'`).
