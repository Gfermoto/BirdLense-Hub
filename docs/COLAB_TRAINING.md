# Дообучение в Google Colab Free — пошаговая инструкция

Полная инструкция для тех, кто никогда не использовал Colab. Обучение классификатора птиц на GPU T4 бесплатно.

---

## Что понадобится

- Аккаунт Google (Gmail)
- Датасет `merged_cls` на вашем компьютере (см. [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md))
- ~2–3 GB свободного места в Google Drive

---

## Часть 1: Подготовка датасета (на вашем компьютере)

### 1.1 Создать датасет (если ещё нет)

На компьютере в папке BirdLense:

```bash
# Активировать venv и запустить полный пайплайн
cd BirdLense
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
cd BirdLense
zip -r merged_cls.zip datasets/merged_cls
```

Или из папки датасета:
```bash
cd BirdLense/datasets
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
    if os.path.exists(train_path):
        n_classes = len(os.listdir(train_path))
        print(f"✅ Датасет распакован: {DATASET_DIR}, классов: {n_classes}")
    else:
        print("⚠️ Проверьте структуру: должны быть папки train/ и val/ с подпапками по классам")
```

Если структура после unzip другая — проверьте в файловом менеджере слева (`📁`): должно быть `train/` и `val/` с подпапками по классам.

---

### Ячейка 3: Установка Ultralytics

```python
!pip install -q ultralytics
print("✅ Ultralytics установлен")
```

---

### Ячейка 4: Обучение

**Параметры для T4 (15 GB):** `batch=64` — если будет ошибка памяти, уменьшите до 32.

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

if os.path.exists(ckpt_path):
    print("🔄 Продолжение с чекпоинта...")
    model = YOLO(ckpt_path)
    model.train(resume=True)
else:
    print("🆕 Начало обучения с нуля...")
    model = YOLO("yolo11n-cls.pt")
    model.train(
        data=DATASET_DIR,
        epochs=150,           # 150 эпох — укладывается в сессию. Для 200 — используйте resume
        imgsz=224,
        batch=64,              # T4: 64. Если OOM — уменьшите до 32
        patience=30,
        project=PROJECT_ROOT,
        name=PROJECT_NAME,
        exist_ok=True,
        device=0,              # GPU
        workers=2,             # Colab: 2 workers достаточно
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

1. Запустите ячейки 1–3 (подключение Drive, распаковка, ultralytics)
2. В ячейке 4 код автоматически найдёт `last.pt` и продолжит с него
3. Запустите ячейку 4 — обучение продолжится

Чекпоинты сохраняются в `Drive/BirdLense_Training/runs/birds_eu_cls_v1/weights/`.

---

## Часть 6: Использование обученной модели в BirdLense

1. Скачайте `best.pt` из Google Drive
2. Скопируйте в BirdLense:
   ```
   best.pt → app/processor/models/classification/nabirds_yolo11n_cls/weights/best.pt
   ```
3. Конвертация в NCNN (если используется NCNN в production):
   - См. [UPGRADE_PLAN.md](./UPGRADE_PLAN.md) или скрипты экспорта Ultralytics
4. Деплой: `make deploy`

---

## Часть 7: Частые проблемы

### «Не удалось подключить GPU»

- **Среда выполнения** → **Сменить среду выполнения** → T4 GPU
- Бесплатный GPU может быть недоступен — попробуйте позже или в другое время суток

### «Out of memory» (OOM)

- Уменьшите `batch` в ячейке 4: с 64 до 32 или 16

### «Файл не найден» при распаковке

- Проверьте имя папки в Drive и `DRIVE_FOLDER`
- Проверьте, что ZIP загружен полностью (без ошибок)

### Сессия отключилась

- Запустите заново ячейки 1–4. Код подхватит `last.pt` и продолжит обучение

---

## Краткий чек-лист

- [ ] Датасет `merged_cls` создан и упакован в ZIP
- [ ] ZIP загружен в Google Drive
- [ ] Colab: Среда выполнения → T4 GPU
- [ ] Ячейки 1–5 выполнены по порядку
- [ ] `best.pt` скачан из Drive
- [ ] Модель скопирована в BirdLense и задеплоена

---

См. также: [FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md), [DATASET_MERGE_FORMAT.md](./DATASET_MERGE_FORMAT.md).
