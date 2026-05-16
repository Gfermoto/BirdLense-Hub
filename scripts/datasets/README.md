# Dataset Scripts

**Paths:** merge по умолчанию → **`datasets/new/detector/yolo/`** (`make dataset-merge-three-class`). Упаковка под Drive: `pack_brg_for_gdrive.py` → **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`** (по умолчанию из `datasets/new/detector/yolo/`). Legacy-папка `scripts/datasets/brg/` опционально. Источники под **`datasets/new/`**: [docs/DATASETS.ru.md](../../docs/DATASETS.ru.md) / [DATASETS.md](../../docs/DATASETS.md).

Scripts for preparing bird detection training datasets. Uses [NABirds](https://dl.allaboutbirds.org/nabirds) as the base dataset.

## EU classifier (приоритет: максимум европейских видов)

Пайплайн **без вырезания классов** для баланса — см. **[EU_CLASSIFIER.md](./EU_CLASSIFIER.md)**.

- **download_birds_eu_merged.py** — скачать [`gfermoto/birds-eu-merged`](https://huggingface.co/datasets/gfermoto/birds-eu-merged) (~490 видов, Scientific (Common))
- **build_eu_classifier_yolo.sh** — скелет сборки (HF + опционально iNat + merge + refine)
- **polish_eu_classifier.sh** — добор EXTRA-слоёв к готовому `yolo_cls_eu_merged` (`--restrict-to-primary-input`, сохранение `test/`)
- **report_classifier_class_counts.py** — классы с малым числом изображений → список на добор (см. раздел «Дополнительные открытые источники» в `EU_CLASSIFIER.md`)

Дополнительный объём: увеличивайте `--max-obs` в **download_inaturalist.py** (`--taxon-id`, `--no-place-filter` для одного вида) и мержите вторым входом в **merge_classification_datasets.py**.

## EU birds: birds-525 + iNaturalist (формат Scientific (Common))

- **download_hf_birds.py** — Hugging Face (birds-525) → YOLO cls, `--format scientific_common`
- **download_inaturalist.py** — iNaturalist Europe API → YOLO cls
- **export_birdlense_to_yolo.py** — BirdLense `app/data/dataset/train` → YOLO cls `train/val` split
- **species_format.py** — утилиты: format, parse, маппинг inat_bird_labels
- **merge_classification_datasets.py** — объединить датасеты
- **refine_classifier_yolo_cls.py** — дедуп между сплитами, опционально нормализация имён папок, выделение `test/`, глобальный дедуп (`--dedupe-global-only`, при необходимости `--skip-rebalance`)
- **backfill_classifier_open.py** — добор редких классов с iNaturalist в staging (без урезания остальных); см. **`EU_CLASSIFIER.md`**
- **balance_classifier_yolo_cls.py** — опциональное **урезание** датасета (subsampling); основной путь баланса — добор, не этот скрипт
- **download_and_merge_all.sh** — полный пайплайн
- **dump_classifier_allowlist.py** — имена классов из `best.pt` → `class_names.txt` для `species.catalog_allowlist_file` в Hub ([CONFIGURATION](../../docs/CONFIGURATION.md))
- **../validate-processor-weights.py** — финальная проверка rollout-кандидата (`best.pt` + `class_names.txt` + `dataset_info.json`)

Формат имён: `Scientific_name (Common Name)` — совпадает с Frigate. См. [docs/DATASETS.md](../docs/DATASETS.md).

## Детектор (Bird / Rodent / Background)

Сборка данных: **`bootstrap_detector_yolo.py`** (`--root datasets/new/detector`) → **`make dataset-merge-three-class`** → **`datasets/new/detector/yolo/`**.

**Один вход целиком (ТЗ Hub):** **`make dataset-build-detector-tz`** — волны A–E, verify binary, merge, dedupe, проверка `yolo/*/labels`.

Усиление качества (второй домен птиц OID **Bird**, hard-negative фон person/dog/cat): **[DETECTOR_DATASET_QUALITY.md](./DETECTOR_DATASET_QUALITY.md)**.

Быстрый большой прогон: **`build_detector_dataset_large.sh`** (числа править внутри).

Тот же объём **волнами**: **`build_detector_dataset_waves.sh`** (см. `DETECTOR_DATASET_QUALITY.md`).

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

## convert_cub_to_yolo.py

Imports **Caltech-UCSD Birds-200-2011** (`bounding_boxes.txt` + official split) into **`binary/birds/`** as YOLO class `0` with filenames prefixed `cub_`. Does **not** download the tarball — unpack locally and pass `--cub-root`. From repo root:

```bash
make dataset-import-cub CUB_ROOT=/path/to/CUB_200_2011
make dataset-merge-three-class
```

## merge_datasets_binary.py

Merges the cleaned NABirds dataset (`nabirds_yolo_cleaned/`) with COCO birds (`coco_birds_yolo/`) and collapses all species into a single "bird" class (class 0). Creates a binary detection dataset for training a general bird detector without species classification.

## merge_datasets_three_class.py ([epic #367](https://github.com/Gfermoto/BirdLense-Hub/issues/367))

Merges **`binary/birds/`** + **`binary/rodent/`** + **`binary/background/`** into выходной каталог (по умолчанию **`datasets/new/detector/yolo/`**) с YOLO class ids **0 = Bird**, **1 = Rodent**, **2 = Background** и `dataset.yaml` в терминах Hub (`Bird` / `Rodent` / `Background`). Background images may use **empty** label files (image-level negatives).

From repo root: **`make dataset-merge-three-class`** читает **`datasets/new/detector/binary/{birds,rodent,background}/`** и пишет **`datasets/new/detector/yolo/`** (см. `Makefile`). Иначе задайте пути вручную в **`merge_datasets_three_class.py`**. Options: `--manifest-out` for a merge audit JSON; see [DATASETS.md](../docs/DATASETS.md). Hard-negative manifest schema: `schemas/hard_negatives_manifest_v1.schema.json`.

Published detector archives (ready for Colab Stage A -> Stage B) are in:
**[gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main)**.

### Dataset quality gates (#394)

After `merge_datasets_three_class.py`, export a profile and run hard checks:

```bash
python3 scripts/datasets/export_detector_dataset_profile.py \
  --dataset-root datasets/new/detector \
  --out /tmp/detector_profile.json

make dataset-verify-quality-gates PROFILE=/tmp/detector_profile.json
```

Verifier script: `scripts/datasets/verify_detector_dataset_quality.py`.
It enforces image/label parity, min train/val counts per class, source diversity,
train imbalance ratio, and background share bounds.

Hard-negatives manifest checks (schema + duplicates + optional file existence):

```bash
make dataset-verify-hard-negatives \
  MANIFEST=scripts/datasets/example_hard_negatives_manifest.json
```

## pack_brg_for_gdrive.py

Собрать **`brg/`** в один ZIP под облако (Google Drive и т.д.): `dataset.yaml`, все сплиты, внутри архива `brg/README_UPLOAD.txt` с командой train. Выход: **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`**.

Стартовые веса **`bl_best.pt`** и состав датасета **`brg`**: [docs/DATASETS.md](../../docs/DATASETS.md) / [DATASETS.ru.md](../../docs/DATASETS.ru.md); Colab: [docs/ML_DETECTOR_COLAB.md](../../docs/ML_DETECTOR_COLAB.md).

```bash
python3 scripts/datasets/pack_brg_for_gdrive.py
python3 scripts/datasets/pack_brg_for_gdrive.py --out /tmp/brg.zip
```

## import_hub_background_folder.py

Локальные кадры фона (например снимки с прод-камеры без животных) → **`binary/background`**: пустые YOLO-лейблы, префикс `hubbg_`, предпочтение полным кадрам вместо `*_thumb*`.

```bash
cd scripts/datasets
python3 import_hub_background_folder.py --source detector/Background
```

## import_roboflow_bird_feeder_birds.py

Импорт ZIP экспорта Roboflow **YOLOv11** (например **[Bird-Feeder, dataset v3](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11)**) в **`datasets/new/detector/binary/birds`**: все виды в разметке → **один класс** `0`, префикс `rfbf_`, `valid/` или `val/` → `val/`. Опционально `--from-url` (если сервер отдаёт 403 — скачайте ZIP в браузере). Лицензия — на карточке проекта.

```bash
make dataset-import-roboflow-bird-feeder ROBOFLOW_ZIP=/path/to/export.zip
```

Или:

```bash
python3 scripts/datasets/import_roboflow_bird_feeder_birds.py \
  --root "$(pwd)/datasets/new/detector" \
  --zip ~/Downloads/bird-feeder-hhjks-3.yolov11.zip
```

Скачивание через **Roboflow Python API** (ключ только в переменной окружения, не в коде и не в git):

```bash
pip install roboflow
export ROBOFLOW_API_KEY='…'   # при утечке ключа — отозвать в app.roboflow.com и выпустить новый
make dataset-download-roboflow-bird-feeder
```

Или: `python3 scripts/datasets/download_roboflow_bird_feeder.py --root "$(pwd)/datasets/new/detector"` (`--skip-import` — только выгрузка в `datasets/downloads/roboflow_bird-feeder-hhjks_v3/`).

## bootstrap_detector_yolo.py

Creates **`binary/birds`**, **`binary/rodent`**, **`binary/background`** and downloads **starter** subsets via **FiftyOne**: COCO 2017 (`bird`), Open Images V6 (`Squirrel`), COCO scenes **without** `bird` for background (empty labels). Large blobs are gitignored — see [DETECTOR_DATASET_QUALITY.md](./DETECTOR_DATASET_QUALITY.md) (структура `binary/`) and [binary/README.md](./binary/README.md).

Requires: `pip install fiftyone pyyaml`

From repo root: **`make bootstrap-detector-data`** (optional: `ARGS='--birds-train 80 …'`).
