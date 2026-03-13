# Dataset Scripts

Scripts for preparing bird detection training datasets. Uses [NABirds](https://dl.allaboutbirds.org/nabirds) as the base dataset.

## EU birds: birds-525 + iNaturalist (формат Scientific (Common))

- **download_hf_birds.py** — Hugging Face (birds-525) → YOLO cls, `--format scientific_common`
- **download_inaturalist.py** — iNaturalist Europe API → YOLO cls
- **species_format.py** — утилиты: format, parse, маппинг inat_bird_labels
- **merge_classification_datasets.py** — объединить датасеты
- **download_and_merge_all.sh** — полный пайплайн

Формат имён: `Scientific_name (Common Name)` — совпадает с Frigate. См. [docs/DATASETS.md](../docs/DATASETS.md).

## convert_nabirds_to_yolo.py

Converts raw NABirds dataset to [Ultralytics YOLO format](https://docs.ultralytics.com/datasets/) used for training.

## remove_unused_classes.py

Removes all classes that don't have actual images from the converted dataset. Needed because NABirds uses a hierarchical class structure where only the leaf nodes have images. Improves model performance and reduces computation.

## convert_nabirds_to_yolo_reduced.py

Similar to `convert_nabirds_to_yolo.py`, but groups gender-specific classes into single classes based on the hierarchy. Results in fewer classes for simpler training. Performance improvement was marginal (~2% mAP50-95), so this dataset is not actively used.

## build_name_hierarchy.py

Converts NABirds' `hierarchy.txt` from `child_id:parent_id` format to `child_name:parent_name` format. The result is used in BirdLense Hub for species categorization.

## convert_oidv4_squirrel_to_yolo.py

Converts OIDv4 dataset (with squirrel class extracted using [OIDv4 Toolkit](https://github.com/EscVM/OIDv4_ToolKit)) to YOLO format. The result is manually merged with NABirds dataset to add squirrel detection.

## download_coco_birds.py

Downloads COCO 2017 dataset filtered to only include images containing birds. Uses `fiftyone` library for efficient download and filtering, then converts to YOLO format.

Requires: `pip install fiftyone pycocotools`

## merge_datasets_binary.py

Merges the cleaned NABirds dataset (`nabirds_yolo_cleaned/`) with COCO birds (`coco_birds_yolo/`) and collapses all species into a single "bird" class (class 0). Creates a binary detection dataset for training a general bird detector without species classification.
