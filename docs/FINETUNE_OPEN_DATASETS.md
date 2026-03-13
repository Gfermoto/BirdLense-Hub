# Дообучение модели на открытых датасетах

Справочник по датасетам и оборудованию. **Пошаговая инструкция:** [COLAB_TRAINING.md](./COLAB_TRAINING.md) — обучение EU-модели в Google Colab Free.

---

## 0. Европейские птицы: текущее положение

**US-модель** (`best_US.pt`): NABirds, ~400 видов, североамериканские. Европейские виды распознаются хуже.

**EU-модель** (в процессе): birds-525 + iNaturalist Europe, ~490 видов. Формат `Scientific (Common)` — совпадает с Frigate/BirdNET. Инструкция: [COLAB_TRAINING.md](./COLAB_TRAINING.md).

**Пока EU не готова:** Frigate Bird Classification (INat) и BirdNET компенсируют отсутствие EU-видов в YOLO.

---

## 1. Текущие модели и пайплайн

| Компонент | Версия | Дообучено на |
|-----------|--------|--------------|
| **Детектор** | YOLOv8n | NABirds + COCO birds + OIDv4 squirrel (бинарный bird/squirrel) |
| **Классификатор US** | YOLOv8n-cls | NABirds (~400 видов, североамериканские) |
| **Классификатор EU** | YOLO11n-cls | birds-525 + iNaturalist Europe (~490 видов) — см. [COLAB_TRAINING.md](./COLAB_TRAINING.md) |

### Двухэтапный пайплайн обучения

1. **Pretrain** — дообучение на открытых датасетах. Цель: расширить охват видов, добавить европейские.
2. **Fine-tune** — дообучение на данных BirdLense Hub (записи с кормушек, подтверждённые/исправленные пользователями). Цель: адаптация к реальным условиям (угол, освещение, кормушка).

### Датасеты для pretrain: европейские vs остальные

| Датасет | Видов | Регион | Ссылка | Улучшение по EU |
|---------|-------|--------|--------|-----------------|
| **[34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species)** | 525 | Частично EU | [Hugging Face](https://huggingface.co/datasets/34data/birds-525-species) | ✅ Частично |
| **iNaturalist (Europe)** | Тысячи | ✅ Европа | [API](https://api.inaturalist.org/v1/docs/), `place_id=96372` | ✅ Да |
| NABirds | ~400 | Северная Америка | [dl.allaboutbirds.org](https://dl.allaboutbirds.org/nabirds) | ❌ Нет европейских видов |
| [sasha/birdsnap](https://huggingface.co/datasets/sasha/birdsnap) | 500 | Северная Америка | [Hugging Face](https://huggingface.co/datasets/sasha/birdsnap) | ❌ Нет европейских видов |
| [randall-lab/cub200](https://huggingface.co/datasets/randall-lab/cub200) | 200 | Северная Америка | [Hugging Face](https://huggingface.co/datasets/randall-lab/cub200) | ❌ Нет европейских видов |
| CUB-200-2011 | 200 | Северная Америка | [Caltech](https://www.vision.caltech.edu/datasets/cub_200_2011/) | ❌ Нет европейских видов |

**NABirds, Birdsnap, CUB-200** — североамериканские датасеты. Добавление их в pretrain **не даст улучшения по европейским видам**, но может усилить общую способность к классификации. Для EU-птиц приоритет: **birds-525** и **iNaturalist Europe**.

---

## 2. Оборудование

### Минимальные требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| **GPU** | 8 GB VRAM (RTX 3060) | 24 GB (RTX 4090, A100) |
| **RAM** | 16 GB | 32 GB |
| **Диск** | 50 GB свободно | 100+ GB (датасеты крупные) |

### Варианты

| Платформа | GPU | Цена | Плюсы |
|-----------|-----|------|-------|
| **RunPod** | RTX 4090, A100 | ~$0.40–0.80/ч | Ноутбуки уже настроены, resume training |
| **Google Colab** | T4 (15 GB) | Бесплатно / Pro $10/мес | Не нужна настройка, ограничения по времени |
| **Локально** | Своя видеокарта | — | Полный контроль, без лимитов |
| **Vast.ai** | Разные | Часто дешевле RunPod | Spot-цены |

**Рекомендация:** [COLAB_TRAINING.md](./COLAB_TRAINING.md) — Colab Free, T4 GPU. Альтернатива: RunPod (`birds_train_cls.ipynb`, batch=256) — 4–8 ч на A100.

---

## 3. Открытые датасеты

### 3.1 Уже в пайплайне BirdLense (используются для текущей модели)

| Датасет | Видов | Регион | Формат | Скрипт |
|---------|-------|--------|--------|--------|
| **NABirds** | ~400 | Северная Америка | YOLO det → cls | `convert_nabirds_to_yolo.py` → `convert_yolo_det_to_cls.py` |
| **COCO birds** | 1 (bird) | — | YOLO | `download_coco_birds.py` — для binary детектора |
| **OIDv4 squirrel** | 1 | — | YOLO | `convert_oidv4_squirrel_to_yolo.py` — для binary |

### 3.2 Hugging Face — для pretrain

| Датасет | Видов | Изображений | Формат | Европейские виды |
|---------|-------|--------------|--------|------------------|
| [34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species) | 525 | ~18k | ImageFolder | ✅ Частично |
| [sasha/birdsnap](https://huggingface.co/datasets/sasha/birdsnap) | 500 | ~50k | bbox + species | ❌ Северная Америка — не даст улучшения по EU |
| [randall-lab/cub200](https://huggingface.co/datasets/randall-lab/cub200) | 200 | ~12k | bbox | ❌ Северная Америка — не даст улучшения по EU |

### 3.3 Внешние — для pretrain (ручная загрузка)

| Датасет | Видов | Ссылка | Европейские |
|---------|-------|--------|-------------|
| **iNaturalist (Europe)** | Тысячи | [API](https://api.inaturalist.org/v1/docs/), `place_id=96372` | ✅ Да — основной источник EU-видов |
| **CUB-200-2011** | 200 | [Caltech](https://www.vision.caltech.edu/datasets/cub_200_2011/) | ❌ Нет — не даст улучшения по EU |

---

## 4. Пайплайн: подготовка → объединение → обучение

### Шаг 1: Скачать и конвертировать датасеты

```
scripts/datasets/
├── download_hf_birds.py           # Hugging Face → YOLO cls (--format scientific_common)
├── download_inaturalist.py       # iNaturalist Europe → YOLO cls (формат Scientific (Common))
├── species_format.py             # Утилиты: format, parse, маппинг inat
├── merge_classification_datasets.py  # Объединить датасеты
└── download_and_merge_all.sh     # Полный пайплайн
```

**Формат имён:** `Scientific_name (Common Name)` — совпадает с Frigate. См. [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md).

**Формат YOLO classification** (ожидает Ultralytics):
```
dataset/
├── train/
│   ├── Eurasian_Jay/
│   │   ├── img1.jpg
│   │   └── img2.jpg
│   ├── Great_Tit/
│   └── ...
└── val/
    ├── Eurasian_Jay/
    └── ...
```

### Шаг 2: Объединение с учётом имён видов

- **Нормализация имён:** `Eurasian Jay` = `Eurasian_Jay` = `Garrulus glandarius` (маппинг)
- **Дубликаты:** один вид может быть в нескольких датасетах — объединять в одну папку
- **Train/val split:** 80/20 или 90/10, стратифицированный по классам

### Шаг 3: Дообучение

```python
# Загрузить ТЕКУЩУЮ модель (не yolov8n-cls.pt с нуля!)
model = YOLO("processor/models/classification/weights/best.pt")
model.train(
    data="merged_dataset/",
    epochs=50,           # Дообучение — меньше эпох
    imgsz=224,
    batch=256,
    patience=15,
    lr0=0.001,           # Ниже LR для fine-tune
    freeze=10,            # Заморозить первые 10 слоёв
    project="YOLO_Cls_Training_Runs",
    name="finetune_european",
)
```

---

## 4. Оценка объёма и времени (birds-525 + iNaturalist EU)

| Датасет | Размер | Время загрузки | Время обучения (A100) |
|---------|--------|-----------------|------------------------|
| NABirds (уже есть) | ~10 GB | — | 4–6 ч |
| birds-525-species | ~0.5 GB | 10 мин | +1 ч |
| iNaturalist Europe | ~2 GB | ~1 ч (rate limit 60/мин) | +1–2 ч |
| **Итого (EU-ориентированный)** | ~13 GB | 2–3 ч | 6–9 ч |

*Birdsnap, CUB-200 — североамериканские, не дают улучшения по европейским видам.*

---

## 5. Чек-лист

**EU-модель (основной способ):**
- [x] `download_hf_birds.py`, `download_inaturalist.py`, `merge_classification_datasets.py`
- [x] `download_and_merge_all.sh` — полный пайплайн
- [ ] [COLAB_TRAINING.md](./COLAB_TRAINING.md) — обучение в Colab, деплой best.pt

**Fine-tune (добавить виды):**
- [ ] COLAB_TRAINING.md, Часть 7 — merge new_species_cls + merged_cls, дообучение на best.pt

**Планируется:**
- [ ] `export_birdlense_to_yolo.py` — экспорт записей BirdLense в YOLO

---

## 6. Ссылки

- [COLAB_TRAINING.md](./COLAB_TRAINING.md) — пошаговая инструкция EU-модели
- [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md) — формат Scientific (Common)
- [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md) — скрипты
- [DATASET_SOURCES.md](./DATASET_SOURCES.md) — источники
