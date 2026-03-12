# Скрипты датасетов и обучения

Краткий справочник. Полный план: [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md).

---

## Подготовка датасетов (`scripts/datasets/`)

| Скрипт | Команда | Зависимости |
|--------|---------|-------------|
| NABirds → YOLO | `python convert_nabirds_to_yolo.py` | NABirds в `./nabirds/` |
| Удалить пустые классы | `python remove_unused_classes.py` | `nabirds_yolo/` |
| COCO → птицы | `python download_coco_birds.py` | `pip install fiftyone pycocotools` |
| Binary (bird/not) | `python merge_datasets_binary.py` | NABirds cleaned + COCO birds |
| Detection → Classification | `python classification/convert_yolo_det_to_cls.py` | Путь в YAML_PATH, OUTPUT_DIR |

---

## Обучение (`scripts/`)

| Ноутбук | Назначение | Платформа |
|---------|------------|-----------|
| `birds_train.ipynb` | Детектор (binary, single-stage) | RunPod |
| `birds_train_cls.ipynb` | Классификатор (yolov8n-cls / yolo11n-cls) | RunPod |

Перед запуском: загрузить датасет (ZIP или gdown), указать `DATASET_DIR`, `PROJECT_NAME`.

---

## Эксперименты (`scripts/experiment/`)

| Скрипт | Назначение |
|--------|------------|
| `compare.py` | Сравнение binary vs single-stage на видео |
| `cp_rand_videos.sh` | Копирование случайных видео |

---

## Модели (`app/processor/models/`)

| Путь | Роль | Версия | Дообучено на |
|------|------|--------|--------------|
| `detection/weights/best.pt` | Бинарный детектор (PyTorch) | YOLOv8n | NABirds + COCO birds + OIDv4 squirrel |
| `classification/weights/best.pt` | Классификатор видов (PyTorch) | YOLOv8n-cls | NABirds (~400 видов, **в основном североамериканские**) |
| `detection/nabirds_yolov8n_ncnn_model/` | Single-stage NCNN (fallback) | YOLOv8n | — |
| `detection/nabirds_yolo11n_binary/` | Binary NCNN (эксперимент) | YOLO11n | — |
| `classification/nabirds_yolo11n_cls/` | Classification NCNN (эксперимент) | YOLO11n-cls | — |

**Текущее:** YOLOv8n, Ultralytics 8.4.21. **Планируется:** переобучение на YOLO11n.

**Пайплайн:** pretrain на открытых датасетах → fine-tune на записях BirdLense. Для европейских видов приоритет: **birds-525** и **iNaturalist Europe**. NABirds, Birdsnap, CUB-200 — североамериканские, не дают улучшения по EU. См. [FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md).

---

## Дообучение на открытых датасетах

См. **[FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md)** — оборудование, датасеты (birds-525, iNaturalist Europe — для EU; NABirds, Birdsnap, CUB-200 — без EU-видов), пайплайн объединения и дообучения.

---

## Планируется

- `export_birdlense_to_yolo.py` — экспорт записей BirdLense Hub в YOLO-формат (см. [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md)).

---

**См. также:** [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md) · [DATASET_SOURCES.md](./DATASET_SOURCES.md) · [HUGGINGFACE_HUB.md](./HUGGINGFACE_HUB.md) · [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) · [scripts/datasets/README.md](../scripts/datasets/README.md)
