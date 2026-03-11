# Дообучение модели на открытых датасетах

Руководство: как дообучить имеющийся классификатор BirdLense на всех доступных открытых датасетах.

---

## 0. Текущая модель и пайплайн

| Компонент | Версия | Дообучено на | Ограничение |
|-----------|--------|--------------|-------------|
| **Детектор** | YOLO11n (Ultralytics 8.4.x) | NABirds + COCO birds + OIDv4 squirrel | Бинарный bird/squirrel |
| **Классификатор** | YOLO11n-cls | NABirds (~400 видов) | **В основном североамериканские птицы** — европейские виды (сойка, синица и т.п.) распознаются хуже |

### Двухэтапный пайплайн обучения

1. **Pretrain** — дообучение на открытых датасетах. Цель: расширить охват видов, добавить европейские.
2. **Fine-tune** — дообучение на данных BirdLense Hub (записи с кормушек, подтверждённые/исправленные пользователями). Цель: адаптация к реальным условиям (угол, освещение, кормушка).

**Планируемые датасеты для pretrain:**

| Датасет | Видов | Регион | Статус |
|---------|-------|--------|--------|
| NABirds | ~400 | Северная Америка | ✅ Используется |
| 34data/birds-525-species | 525 | Частично EU | Планируется |
| sasha/birdsnap | 500 | Северная Америка | Планируется |
| randall-lab/cub200 | 200 | Северная Америка | Планируется |
| iNaturalist | Тысячи | ✅ Фильтр по региону | Планируется |
| CUB-200-2011 | 200 | Северная Америка | Планируется |

---

## 1. Оборудование

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

**Рекомендация:** RunPod — в `birds_train_cls.ipynb` уже есть конфиг (batch=256, workers=6). Загрузка датасета ~10 GB, обучение 200 эпох — ориентировочно 4–8 часов на A100.

---

## 2. Открытые датасеты

### 2.1 Уже в пайплайне BirdLense (используются для текущей модели)

| Датасет | Видов | Регион | Формат | Скрипт |
|---------|-------|--------|--------|--------|
| **NABirds** | ~400 | Северная Америка | YOLO det → cls | `convert_nabirds_to_yolo.py` → `convert_yolo_det_to_cls.py` |
| **COCO birds** | 1 (bird) | — | YOLO | `download_coco_birds.py` — для binary детектора |
| **OIDv4 squirrel** | 1 | — | YOLO | `convert_oidv4_squirrel_to_yolo.py` — для binary |

### 2.2 Hugging Face — планируется для pretrain

| Датасет | Видов | Изображений | Формат | Европейские виды |
|---------|-------|--------------|--------|------------------|
| [34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species) | 525 | ~18k | ImageFolder | Частично |
| [sasha/birdsnap](https://huggingface.co/datasets/sasha/birdsnap) | 500 | ~50k | bbox + species | Северная Америка |
| [randall-lab/cub200](https://huggingface.co/datasets/randall-lab/cub200) | 200 | ~12k | bbox | Северная Америка |

### 2.3 Внешние — планируется для pretrain (ручная загрузка)

| Датасет | Видов | Ссылка | Европейские |
|---------|-------|--------|-------------|
| **iNaturalist** | Тысячи | [API](https://api.inaturalist.org/v1/docs/) | ✅ Фильтр по региону |
| **CUB-200-2011** | 200 | [Caltech](https://www.vision.caltech.edu/datasets/cub_200_2011/) | Нет |

---

## 3. Пайплайн: подготовка → объединение → обучение

### Шаг 1: Скачать и конвертировать датасеты

```
scripts/datasets/
├── 1_nabirds.py                    # NABirds → YOLO (уже есть)
├── download_hf_birds.py           # НОВЫЙ: Hugging Face → YOLO cls
│   # --dataset 34data/birds-525-species --output birds_525_cls
│   # --dataset sasha/birdsnap --output birdsnap_cls
├── merge_classification_datasets.py  # Объединить датасеты в один
│   # --inputs nabirds_cls birds_525_cls --output merged_cls
└── merge_all_cls.py               # НОВЫЙ: объединить в один dataset/
```

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
# Загрузить ТЕКУЩУЮ модель (не yolo11n-cls.pt с нуля!)
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

## 4. Скрипты для добавления

### 4.1 Загрузка 34data/birds-525-species (Hugging Face)

```python
# scripts/datasets/download_hf_birds_525.py
from datasets import load_dataset
from pathlib import Path

ds = load_dataset("34data/birds-525-species", split="train")
out = Path("datasets/birds_525_cls")
for item in ds:
    label = item["labels"]  # или как в датасете
    (out / "train" / label).mkdir(parents=True, exist_ok=True)
    item["image"].save(out / "train" / label / f"{item['id']}.jpg")
```

### 4.2 iNaturalist (европейские птицы)

```python
# API: GET https://api.inaturalist.org/v1/observations
# Параметры: taxon_id=3 (Aves), place_id=... (Europe), quality_grade=research
# Скачать изображения по observation_photos
```

Документация: [iNaturalist API](https://api.inaturalist.org/v1/docs/)

### 4.3 Birdsnap (bbox → crops)

Аналогично `convert_yolo_det_to_cls.py`: есть bbox в `images.txt`, вырезать crops и сохранить в `train/Species_Name/`.

---

## 5. Оценка объёма и времени

| Датасет | Размер | Время загрузки | Время обучения (A100) |
|---------|--------|-----------------|------------------------|
| NABirds (уже есть) | ~10 GB | — | 4–6 ч |
| birds-525-species | ~0.5 GB | 10 мин | +1 ч |
| Birdsnap | ~5 GB | 30 мин | +2–3 ч |
| iNaturalist (500 видов EU) | ~2 GB | 1 ч | +1–2 ч |
| **Итого** | ~18 GB | 2–3 ч | 8–12 ч |

---

## 6. Чек-лист

**Pretrain (открытые датасеты):**
- [ ] RunPod/Colab: создать pod, загрузить `birds_train_cls.ipynb`
- [ ] Скачать NABirds (или использовать уже подготовленный `nabirds_yolo_cleaned_cls`)
- [ ] Добавить скрипт загрузки Hugging Face (birds-525, birdsnap) — `download_hf_birds.py`
- [ ] Добавить скрипт iNaturalist для европейских видов
- [ ] Скрипт `merge_classification_datasets.py` — объединить датасеты
- [ ] В `birds_train_cls.ipynb`: загрузить `best.pt`, дообучить на merged dataset

**Fine-tune (данные BirdLense):**
- [ ] Реализовать `export_birdlense_to_yolo.py` — экспорт записей в YOLO
- [ ] Собрать подтверждённые/исправленные детекции с кормушек
- [ ] Дообучить pretrain-модель на данных BirdLense (меньше эпох, ниже LR)

**Деплой:**
- [ ] Экспорт: `best.pt` → `processor/models/classification/weights/`
- [ ] Деплой и проверка

---

## 7. Ссылки

- [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md) — общий план
- [DATASET_SOURCES.md](./DATASET_SOURCES.md) — источники
- [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md) — скрипты
- [RunPod](https://runpod.io) — GPU cloud
- [iNaturalist API](https://api.inaturalist.org/v1/docs/)
