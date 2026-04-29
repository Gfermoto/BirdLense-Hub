# Обучение EU-модели в Google Colab

**Детектор (YOLO detection) в Colab:** [ML_DETECTOR_COLAB.ru.md](./ML_DETECTOR_COLAB.ru.md).  
ZIP-архивы датасета детектора опубликованы в [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) (balanced + full, Stage A -> Stage B).  
**Итог по ML в репозитории и ваши шаги:** [ML_OPERATOR_HANDOFF.ru.md](./ML_OPERATOR_HANDOFF.ru.md).

[English](./TRAINING.md)

---

Пошаговая инструкция: классификатор птиц на GPU T4 бесплатно. Датасеты и скрипты: [DATASETS](./DATASETS.ru.md).

---

## Что обучаем и зачем

**Текущая модель в Hub** — **`classification/weights/best.pt`** (EU, [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu), ~491 вид). US (NABirds) — резерв в `best_US.pt`.

**Обучение EU-модели** (для обновления или fine-tune): классификатор на **европейских** видах:
- **birds-525** (Hugging Face) — 525 видов птиц в формате Scientific (Common)
- **iNaturalist Europe** — наблюдения из Европы (place_id: Europe)

После merge получается ~490 видов (классы с изображениями в обоих сплитах). Больше, чем в US-модели: та обучена на **NABirds** — датасете с ~400 видами Северной Америки. EU-модель — все ~490 видов релевантны для Европы.

Формат имён `Scientific (Common)` совпадает с Frigate и BirdNET — упрощает слияние детекций.

**Резервная копия:** US — `best_US.pt`. Активный EU-файл в конфиге — **`processor.models.classifier` → `models/classification/weights/best.pt`** (тот же файл, что на Hugging Face под именем `best.pt`). US: `cp best_US.pt` поверх `best.pt` и выровнять `class_names.txt`.

---

## Что понадобится

- Аккаунт Google (Gmail)
- Датасет `merged_cls` (см. [DATASETS](./DATASETS.ru.md))
- ~2–3 GB свободного места в Google Drive

---

## Часть 1: Подготовка датасета (на вашем компьютере)

### 1.1 Создать датасет (если ещё нет)

На компьютере в папке BirdLense:

```bash
# Активировать venv и запустить полный пайплайн
cd BirdLense-Hub   # корень репозитория (имя папки может быть своим)
.venv-datasets/bin/python scripts/datasets/download_hf_birds.py \
  --dataset 34data/birds-525-species \
  --output datasets/birds_525_cls \
  --format scientific_common

.venv-datasets/bin/python scripts/datasets/download_inaturalist.py \
  --output datasets/inaturalist_europe_cls \
  --max-obs 2000

.venv-datasets/bin/python scripts/datasets/merge_classification_datasets.py \
  --inputs datasets/birds_525_cls datasets/inaturalist_europe_cls \
  --output datasets/merged_cls \
  --val-ratio 0.2
```

Или использовать готовый `datasets/merged_cls`, если он уже есть.

### 1.2 Упаковать в ZIP

```bash
cd BirdLense-Hub   # корень репозитория
zip -r merged_cls.zip datasets/merged_cls
```

Или из папки датасета:
```bash
cd BirdLense-Hub/datasets
zip -r merged_cls.zip merged_cls
```

Файл `merged_cls.zip` (~500 MB – 2 GB) — это то, что нужно загрузить в Drive.

---

## Часть 2: Загрузка в Google Drive

1. Откройте [drive.google.com](https://drive.google.com)
2. Создайте папку, например `BirdLense_Training`
3. Перетащите `merged_cls.zip` в эту папку
4. Дождитесь окончания загрузки

---

## Часть 3: Google Colab — первый запуск

### 3.1 Открыть Colab

1. Перейдите на [colab.research.google.com](https://colab.research.google.com)
2. Войдите в аккаунт Google
3. **Файл** → **Создать блокнот** (или **New notebook**)

### 3.2 Включить GPU

1. В меню: **Среда выполнения** → **Сменить среду выполнения** (или **Runtime** → **Change runtime type**)
2. **Тип оборудования:** выберите **T4 GPU**
3. Нажмите **Сохранить**

Проверка: в следующей ячейке выполните `!nvidia-smi` — должна отобразиться информация о GPU T4.

---

## Часть 4: Ячейки ноутбука (копировать по порядку)

Создайте ячейки и выполните их **по очереди** (Shift+Enter).

---

### Ячейка 1: Подключить Google Drive

```python
# Подключаем Google Drive — датасет и результаты будут храниться там
from google.colab import drive
drive.mount('/content/drive')
```

При первом запуске откроется окно: разрешите доступ к Drive. Нажмите ссылку, выберите аккаунт, скопируйте код и вставьте в поле.

---

### Ячейка 2: Пути и распаковка датасета

**Важно:** замените `BirdLense_Training` на имя вашей папки в Drive, если оно другое.

```python
import os
import shutil

# === НАСТРОЙКИ — ИЗМЕНИТЕ ПОД СЕБЯ ===
DRIVE_FOLDER = "BirdLense_Training"   # Папка в Google Drive
ZIP_NAME = "merged_cls.zip"           # Имя архива с датасетом
PROJECT_NAME = "birds_eu_cls_v1"       # Имя проекта (папка с результатами)
# ======================================

# Пути
DRIVE_ROOT = "/content/drive/MyDrive"
DRIVE_PATH = os.path.join(DRIVE_ROOT, DRIVE_FOLDER)
ZIP_PATH = os.path.join(DRIVE_PATH, ZIP_NAME)
DATASET_DIR = "/content/merged_cls"  # Распакуем сюда (быстрее чем с Drive)
PROJECT_ROOT = os.path.join(DRIVE_PATH, "runs")  # Результаты сохраняем в Drive

# Проверка
if not os.path.exists(ZIP_PATH):
    print(f"❌ Не найден: {ZIP_PATH}")
    print("Проверьте DRIVE_FOLDER и ZIP_NAME. Содержимое Drive:")
    if os.path.exists(DRIVE_ROOT):
        for f in os.listdir(DRIVE_ROOT):
            print(f"  - {f}")
else:
    print(f"✅ Найден: {ZIP_PATH}")
    # Распаковка (zip создан как: zip -r merged_cls.zip datasets/merged_cls)
    !unzip -q -o "{ZIP_PATH}" -d /content/
    # Путь после unzip (зависит от структуры zip)
    for p in ["/content/datasets/merged_cls", "/content/merged_cls", "/content/merged_cls/merged_cls"]:
        if os.path.exists(p) and os.path.exists(os.path.join(p, "train")):
            DATASET_DIR = p
            break
    train_path = os.path.join(DATASET_DIR, "train")
    val_path = os.path.join(DATASET_DIR, "val")
    if os.path.exists(train_path):
        # Исправить датасет: YOLO требует одинаковое число классов в train и val
        def has_images(p):
            return any(f.lower().endswith(('.jpg','.jpeg','.png','.webp')) for f in os.listdir(p))
        train_classes = {d for d in os.listdir(train_path) if os.path.isdir(os.path.join(train_path, d)) and has_images(os.path.join(train_path, d))}
        val_classes = {d for d in os.listdir(val_path) if os.path.isdir(os.path.join(val_path, d)) and has_images(os.path.join(val_path, d))} if os.path.exists(val_path) else set()
        valid = train_classes & val_classes
        for c in list(os.listdir(train_path)):
            if c not in valid and os.path.isdir(os.path.join(train_path, c)):
                shutil.rmtree(os.path.join(train_path, c), ignore_errors=True)
        for c in list(os.listdir(val_path)) if os.path.exists(val_path) else []:
            if c not in valid and os.path.isdir(os.path.join(val_path, c)):
                shutil.rmtree(os.path.join(val_path, c), ignore_errors=True)
        n_classes = len(valid)
        if len(train_classes) != n_classes or len(val_classes) != n_classes:
            print(f"⚠️ Удалены классы без изображений в обоих сплитах. Осталось: {n_classes}")
        print(f"✅ Датасет распакован: {DATASET_DIR}, классов: {n_classes}")
    else:
        print("⚠️ Проверьте структуру: должны быть папки train/ и val/ с подпапками по классам")
```

Если структура после unzip другая — проверьте в файловом менеджере слева (`📁`): должно быть `train/` и `val/` с подпапками по классам.

---

### Ячейка 3: Установка Ultralytics

```python
# Важно: 8.3.203+ исправляет ошибку GradScaler при resume
!pip install -q -U ultralytics
print("✅ Ultralytics установлен")
```

---

### Ячейка 4: Обучение

**Параметры для T4 (15 GB):** `batch=64` — если будет ошибка памяти, уменьшите до 32.

**Время:** ~2.5 мин/эпоху на GPU → 100 эпох ≈ 4 ч (рекомендуется), 150 ≈ 6–7 ч. На CPU — в 10–20 раз дольше. Colab Free может отключиться — используйте resume (см. выше).

**Важно:** замените `BirdLense_Training` на имя вашей папки в Drive.

```python
from ultralytics import YOLO
import os

# Пути
for p in ["/content/datasets/merged_cls", "/content/merged_cls"]:
    if os.path.exists(p) and os.path.exists(os.path.join(p, "train")):
        DATASET_DIR = p
        break
else:
    DATASET_DIR = "/content/datasets/merged_cls"  # по умолчанию

PROJECT_ROOT = "/content/drive/MyDrive/BirdLense_Training/runs"  # Измените под свою папку
PROJECT_NAME = "birds_eu_cls_v1"

os.makedirs(PROJECT_ROOT, exist_ok=True)
ckpt_path = os.path.join(PROJECT_ROOT, PROJECT_NAME, "weights", "last.pt")

# device=0 — GPU, device='cpu' — CPU (если GPU недоступен). batch меньше на CPU
DEVICE = 0 if __import__('torch').cuda.is_available() else 'cpu'
BATCH = 64 if DEVICE != 'cpu' else 16
EPOCHS = 100  # 80–100 достаточно (плато к 50–60). См. секцию «Эпохи» ниже

if os.path.exists(ckpt_path):
    print("🔄 Продолжение с чекпоинта...")
    model = YOLO(ckpt_path)
    # amp=False — если ошибка "GradScaler state dict is empty" (старый чекпоинт без AMP)
    model.train(resume=True, device=DEVICE, epochs=EPOCHS, amp=False)
else:
    print("🆕 Начало обучения с нуля...")
    model = YOLO("yolo11n-cls.pt")
    model.train(
        data=DATASET_DIR,
        epochs=EPOCHS,        # 80–100 достаточно для merged_cls
        imgsz=224,
        batch=BATCH,          # T4: 64. CPU: 16. Если OOM — уменьшите
        patience=30,
        project=PROJECT_ROOT,
        name=PROJECT_NAME,
        exist_ok=True,
        device=DEVICE,        # 0=GPU, 'cpu'=CPU
        workers=2,            # Colab: 2 workers достаточно
    )
```

---

### Ячейка 5: Сохранить результаты и скачать best.pt

```python
import shutil
import os

# Те же пути, что в ячейках 2 и 4
DRIVE_FOLDER = "BirdLense_Training"  # Измените если другая папка
PROJECT_ROOT = f"/content/drive/MyDrive/{DRIVE_FOLDER}/runs"
PROJECT_NAME = "birds_eu_cls_v1"
DRIVE_PATH = f"/content/drive/MyDrive/{DRIVE_FOLDER}"
source_dir = os.path.join(PROJECT_ROOT, PROJECT_NAME)

if os.path.exists(source_dir):
    best_pt = os.path.join(source_dir, "weights", "best.pt")
    if os.path.exists(best_pt):
        # Копируем в Drive для удобного скачивания
        drive_dest = os.path.join(DRIVE_PATH, "best.pt")
        shutil.copy(best_pt, drive_dest)
        print(f"✅ best.pt сохранён в Drive: {drive_dest}")
        print("Скачать: откройте Drive → BirdLense_Training → best.pt → ПКМ → Скачать")
    else:
        print("⏳ Обучение не завершено. best.pt появится после завершения.")
else:
    print("❌ Папка с результатами не найдена.")
```

---

## Часть 5: Продолжение обучения (если сессия прервалась)

Colab отключает через ~12 часов. Если обучение не закончилось:

1. **Запустите ячейки 1–4 по порядку.** При новой сессии `/content` очищается — датасет исчезает. Ячейка 2 (распаковка) обязательна, иначе «no training images found».
2. В ячейке 4 код автоматически найдёт `last.pt` в Drive и продолжит с него
3. Обучение продолжится с последней эпохи

Чекпоинты сохраняются в `Drive/BirdLense_Training/runs/birds_eu_cls_v1/weights/`.

### Обучение завершено, но хочу ещё эпох

**Важно:** для merged_cls плато достигается к 50–60 эпохам. `best.pt` уже сохранён на лучшей эпохе — **добавлять эпохи не нужно**, используйте `best.pt` как есть.

Если всё же нужно дообучить (другой датасет, эксперимент) и появилась ошибка *«training to N epochs is finished, nothing to resume»* — дообучайте **без** `resume=True`, с **низким LR** (`lr0=0.0001`):

```python
model = YOLO(".../last.pt")
model.train(
    data=DATASET_DIR,
    epochs=50,
    lr0=0.0001,       # обязательно низкий LR, иначе метрики ухудшатся
    imgsz=224,
    batch=64,
    patience=15,
    project=".../runs",
    name="birds_eu_cls_v1_cont",
    exist_ok=True,
    device=0,
    workers=2,
    amp=False,
)
```

Результат: `birds_eu_cls_v1_200ep/weights/best.pt`.

---

## Часть 5.1: Резервная копия — что перенести с Drive

Чтобы продолжить обучение с того же места (другой Colab, другой компьютер):

### С Drive скачать

| Файл | Назначение |
|------|------------|
| `BirdLense_Training/runs/birds_eu_cls_v1/weights/last.pt` | Чекпоинт для resume — продолжить с последней эпохи |
| `BirdLense_Training/runs/birds_eu_cls_v1/weights/best.pt` | Лучшая модель (если обучение завершено) |
| `BirdLense_Training/best.pt` | Копия best.pt в корне папки (из ячейки 5) |
| `BirdLense_Training/merged_cls.zip` | Датасет (или качать с Hugging Face, если загрузили) |

**Минимум для resume:** `last.pt` + `merged_cls.zip` (или HF) + ноутбук.

### Ноутбук

1. В Colab: **Файл** → **Сохранить копию на Drive** — автосохранение в Drive
2. Или **Файл** → **Скачать** → **Скачать .ipynb** — сохранить локально
3. Можно положить в `BirdLense/scripts/` (например `birds_eu_colab.ipynb`) для версионирования

### Перенос на другой Colab

1. Загрузите `last.pt` и `merged_cls.zip` в новую папку Drive
2. В ячейке 2 и 4 укажите путь к этой папке (`DRIVE_FOLDER`)
3. Откройте сохранённый .ipynb в Colab (File → Open notebook → Upload)

---

## Часть 6: Использование обученной модели в BirdLense

1. Скачайте `best.pt`:
   - **Google Drive** — из папки BirdLense_Training (файл весов обычно называется `best.pt`)
   - **Hugging Face** — [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) → Files → best.pt → Download
2. Скопируйте в BirdLense:
   ```
   best.pt (с HF/Colab) → `app/processor/models/classification/weights/best.pt`
   ```
   (заменит текущую модель; US — резерв в `best_US.pt`)
3. Конвертация в NCNN (если на **x86/amd64** используется `single_stage` / NCNN):
   - См. [ROADMAP](./ROADMAP.ru.md) или скрипты экспорта Ultralytics. ARM не является целевой платформой.
4. Деплой: `make deploy`

---

## Часть 7: Fine-tune — добавить новые виды (сойка, синицы, воробьи, поползень)

Дообучение **без обучения с нуля**: загружаем `best.pt` и дообучаем на старых + новых классах.

### 7.1 Подготовка датасета с новыми видами

Формат папок — `Scientific (Common)` (как в merged_cls):

```
datasets/new_species_cls/
├── train/
│   ├── Garrulus glandarius (Eurasian Jay)/     # сойка
│   ├── Parus major (Great Tit)/                # большая синица
│   ├── Cyanistes caeruleus (Eurasian Blue Tit)/# лазоревка
│   ├── Passer domesticus (House Sparrow)/      # домовый воробей
│   ├── Sitta europaea (Eurasian Nuthatch)/     # поползень
│   └── ...
└── val/
    └── (те же классы, 20% изображений)
```

Соберите фото (свои с кормушки, iNaturalist, Google Images) — минимум 20–30 на вид в train и 5+ в val. Если вид уже есть в merged_cls — merge добавит к нему новые изображения.

### 7.2 Объединение с основным датасетом

```bash
python scripts/datasets/merge_classification_datasets.py \
  --inputs datasets/merged_cls datasets/new_species_cls \
  --output datasets/merged_cls_extended \
  --val-ratio 0.2
```

### 7.3 Дообучение в Colab

В ячейке 4 **замените** код: загружайте `best.pt` (не `yolo11n-cls.pt`), датасет — `merged_cls_extended`, меньше эпох, ниже LR:

```python
from ultralytics import YOLO
import os

# Загрузить обученную модель (не с нуля!)
BEST_PT = "/content/drive/MyDrive/BirdLense_Training/best.pt"  # или runs/.../weights/best.pt
DATASET_DIR = "/content/datasets/merged_cls_extended"  # старые + новые виды

model = YOLO(BEST_PT)
model.train(
    data=DATASET_DIR,
    epochs=30,            # Fine-tune — меньше эпох
    imgsz=224,
    batch=64,
    lr0=0.001,           # Ниже LR для дообучения
    patience=10,
    project="/content/drive/MyDrive/BirdLense_Training/runs",
    name="birds_eu_cls_finetune",
    exist_ok=True,
    device=0,            # или 'cpu'
)
```

Сначала распакуйте `merged_cls_extended.zip` (или соберите датасет в Colab). Результат — `best.pt` с расширенным набором видов.

### 7.4 Дообучение на BirdLense экспорте (birdlense_ready)

**Структура в Google Drive:**

```
BirdLense_Annotations/
├── birdlense_ready.zip   # Датасет (train/val)
└── best.pt               # Текущая модель
```

**Colab — ячейки для дообучения:**

```python
# Ячейка 1: Подключить Drive
from google.colab import drive
drive.mount('/content/drive')
```

```python
# Ячейка 2: Распаковка (zip содержит datasets/birdlense_ready/)
import os
DRIVE_FOLDER = "BirdLense_Annotations"
ZIP_NAME = "birdlense_ready.zip"
DRIVE_PATH = f"/content/drive/MyDrive/{DRIVE_FOLDER}"
ZIP_PATH = os.path.join(DRIVE_PATH, ZIP_NAME)

!unzip -q -o "{ZIP_PATH}" -d /content/
# Путь после распаковки: /content/datasets/birdlense_ready/
DATASET_DIR = "/content/datasets/birdlense_ready"
if not os.path.exists(os.path.join(DATASET_DIR, "train")):
    DATASET_DIR = "/content/birdlense_ready"  # если zip пересобран с другой структурой
print(f"Датасет: {DATASET_DIR}")
```

```python
# Ячейка 3: Ultralytics
!pip install -q -U ultralytics
```

```python
# Ячейка 4: Дообучение
from ultralytics import YOLO

BEST_PT = f"/content/drive/MyDrive/BirdLense_Annotations/best.pt"
DATASET_DIR = "/content/datasets/birdlense_ready"  # путь после unzip (zip содержит datasets/birdlense_ready/)

model = YOLO(BEST_PT)
model.train(
    data=DATASET_DIR,
    epochs=30,
    imgsz=224,
    batch=64,
    lr0=0.001,
    patience=10,
    project=f"/content/drive/MyDrive/BirdLense_Annotations/runs",
    name="birds_finetune",
    exist_ok=True,
    device=0,
    workers=2,
)
```

```python
# Ячейка 5: Сохранить best.pt
import shutil
best = "/content/drive/MyDrive/BirdLense_Annotations/runs/birds_finetune/weights/best.pt"
if os.path.exists(best):
    shutil.copy(best, "/content/drive/MyDrive/BirdLense_Annotations/best_finetuned.pt")
    print("✅ best_finetuned.pt сохранён в Drive")
```

**После обучения:** скачайте `best_finetuned.pt` → скопируйте в `app/processor/models/classification/weights/best.pt` → `make deploy`.

---

## Часть 8: Частые проблемы

### «Не удалось подключить GPU»

- **Среда выполнения** → **Сменить среду выполнения** → T4 GPU
- Бесплатный GPU может быть недоступен — попробуйте позже или в другое время суток

### «Out of memory» (OOM)

- Уменьшите `batch` в ячейке 4: с 64 до 32 или 16

### «Файл не найден» при распаковке

- Проверьте имя папки в Drive и `DRIVE_FOLDER`
- Проверьте, что ZIP загружен полностью (без ошибок)

### Сессия отключилась / GPU отключили / «no training images found»

- Colab Free может отключить GPU или runtime в любой момент — лимиты динамические ([FAQ](https://research.google.com/colaboratory/faq.html#usage-limits))
- `/content` очищается при новой сессии — датасет нужно распаковать заново
- Запустите ячейки 1–4 по порядку (включая ячейку 2 — распаковку). Код подхватит `last.pt` и продолжит обучение

### «training to N epochs is finished, nothing to resume»

Обучение уже завершено (все эпохи пройдены). Для merged_cls добавлять эпохи не нужно (плато к 50–60). Если нужно — см. «Обучение завершено, но хочу ещё эпох» в Части 5.

### «GradScaler state dict is empty» при resume

Ошибка возникает, если чекпоинт сохранён без AMP (или старой версией ultralytics). Решения (по порядку):

1. **Патч чекпоинта** — удалить пустой scaler (часто помогает):
   ```python
   import torch, shutil
   ckpt_path = "/content/drive/MyDrive/BirdLense_Training/runs/birds_eu_cls_v1/weights/last.pt"
   ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
   if "scaler" in ckpt and (ckpt["scaler"] is None or len(ckpt.get("scaler", {})) == 0):
       shutil.copy(ckpt_path, ckpt_path + ".backup")
       del ckpt["scaler"]
       torch.save(ckpt, ckpt_path)
   ```
2. **Обновить ultralytics:** `!pip install -U ultralytics` (8.3.203+ корректно обрабатывает старые чекпоинты)
3. **Отключить AMP при resume:** `model.train(resume=True, ..., amp=False)` — уже добавлено в пример выше

---

## Краткий чек-лист

- [ ] Датасет `merged_cls` создан и упакован в ZIP
- [ ] ZIP загружен в Google Drive
- [ ] Colab: Среда выполнения → T4 GPU
- [ ] Ячейки 1–5 выполнены по порядку
- [ ] `best.pt` скачан из Drive или Hugging Face
- [ ] Модель скопирована в `classification/weights/best.pt` и задеплоена
- [ ] Резерв US: `best_US.pt` в `classification/weights/`

---

## Эпохи (80–100 достаточно)

По эмпирике merged_cls: плато к **50–60 эпохам**, top1 ~85.3%. 80–100 эпох хватает (~3–4 ч на T4). 150+ — лишнее время. Переобучать с нуля не нужно, если есть `best.pt`.

---

## Hugging Face — датасеты и модели

**Репозитории:** [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged) (датасет), [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) (best.pt), [gfermoto/birdlense-annotations](https://huggingface.co/datasets/gfermoto/birdlense-annotations) (разметка).

**Токен:** [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → Write → `huggingface-cli login`.

**Загрузка датасета:** Web UI или `huggingface-cli upload gfermoto/birds-eu-merged merged_cls.zip . --repo-type dataset`. **Скачать в Colab:** `hf_hub_download(repo_id="gfermoto/birds-eu-merged", filename="merged_cls.zip", repo_type="dataset")`.

**Загрузка best.pt:** `huggingface-cli upload gfermoto/birdlense-birds-eu best.pt .`. **Скачать в BirdLense:** `huggingface-cli download gfermoto/birdlense-birds-eu best.pt --local-dir app/processor/models/classification/weights`.

**Model card:** `datasets: - gfermoto/birds-eu-merged`, `tags: image-classification, birds, europe, birdlense, yolo`. Лимиты: 50 GB датасеты, 10 GB модели (бесплатно).

---

См. также: [DATASETS](./DATASETS.ru.md).
