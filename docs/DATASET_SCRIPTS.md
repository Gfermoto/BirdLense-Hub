# Скрипты датасетов и обучения

Краткий справочник. Полный план: [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md).

---

## Подготовка датасетов (`scripts/datasets/`)

### EU-классификатор (birds-525 + iNaturalist)

| Скрипт | Назначение |
|--------|------------|
| `download_hf_birds.py` | Hugging Face → YOLO cls (--format scientific_common) |
| `download_inaturalist.py` | iNaturalist Europe → YOLO cls |
| `merge_classification_datasets.py` | Объединить датасеты (формат Scientific (Common)) |
| `download_and_merge_all.sh` | Полный пайплайн: birds-525 + iNaturalist → merged_cls |

**Инструкция:** [COLAB_TRAINING.md](./COLAB_TRAINING.md) · [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md)

### Детектор, NABirds (legacy)

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
| `classification/weights/best.pt` | Классификатор (PyTorch) | YOLO11n-cls | EU: birds-525 + iNaturalist (~490 видов). Или US: NABirds (~400) |
| `classification/weights/best_US.pt` | Резервная копия US-модели (NABirds) | — | `cp best_US.pt best.pt` — вернуть US |
| `detection/nabirds_yolov8n_ncnn_model/` | Single-stage NCNN (fallback) | YOLOv8n | — |
| `detection/nabirds_yolo11n_binary/` | Binary NCNN (эксперимент) | YOLO11n | — |
| `classification/nabirds_yolo11n_cls/` | Classification NCNN (эксперимент) | YOLO11n-cls | — |

**Текущее:** Ultralytics 8.4.21. EU-модель — YOLO11n-cls, обучение: [COLAB_TRAINING.md](./COLAB_TRAINING.md).

---

## Планируется

- `export_birdlense_to_yolo.py` — экспорт записей BirdLense в YOLO (см. [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md))

---

**См. также:** [COLAB_TRAINING.md](./COLAB_TRAINING.md) · [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md) · [FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md) · [scripts/datasets/README.md](../scripts/datasets/README.md)
