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
| `birds_train_cls.ipynb` | Классификатор (yolo11n-cls) | RunPod |

Перед запуском: загрузить датасет (ZIP или gdown), указать `DATASET_DIR`, `PROJECT_NAME`.

---

## Эксперименты (`scripts/experiment/`)

| Скрипт | Назначение |
|--------|------------|
| `compare.py` | Сравнение binary vs single-stage на видео |
| `cp_rand_videos.sh` | Копирование случайных видео |

---

## Модели (`app/processor/models/`)

| Путь | Роль |
|------|------|
| `detection/weights/best.pt` | Бинарный детектор (PyTorch) |
| `classification/weights/best.pt` | Классификатор видов (PyTorch) |
| `detection/nabirds_yolo11n_binary/` | Binary NCNN (RPi) |
| `classification/nabirds_yolo11n_cls/` | Classification NCNN (RPi) |

---

## Планируется

- `export_birdlense_to_yolo.py` — экспорт записей BirdLense Hub в YOLO-формат (см. [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md)).

---

**См. также:** [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md) · [DATASET_SOURCES.md](./DATASET_SOURCES.md) · [scripts/datasets/README.md](../scripts/datasets/README.md)
