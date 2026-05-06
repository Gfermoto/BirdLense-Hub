# Обучение детектора (YOLO) в Google Colab

[English](./ML_DETECTOR_COLAB.md)

Классификатор — [TRAINING.ru.md](./TRAINING.ru.md). Здесь только **детекция** (`dataset.yaml`). Пути к **`brg/`**, merge, упаковка ZIP — [DATASETS.ru.md](./DATASETS.ru.md).

**Режим по умолчанию (рекомендуется):** дообучение **от последних боевых весов хаба** — тот же **`best.pt`**, который сейчас в проде (то же дерево классов Bird / Rodent / Background и тот же **YOLO11n-detect**, что ожидает процессор). На Drive этот файл кладём как **`bl_best.pt`**, чтобы он не смешался с **`best.pt`** из новых ранов Ultralytics.

**Не использовать здесь как старт части A:** готовые веса **COCO** (`yolo11n.pt` и т.п.) — **80 классов**, контракт с хабом и постобработкой ломается. Холодный старт без чекпоинта см. блок в конце части **A**.

---

## Оглавление

| Часть | О чём |
|--------|--------|
| **A** | Основной сценарий: **`brg` ZIP**, старт **`bl_best.pt`** (копия боевого **`best.pt`** с хаба), два этапа (`freeze` → full), OpenVINO **640** — до выгрузки на хаб |
| **B** | Дополнительно: старый **binary** пайплайн с Hugging Face (balanced → full, **`yolo11n.pt`**, **960**) |
| **C** | Контракт классов, проверка перед продом |

---

# Часть A — Основной сценарий (`brg` + боевые веса)

## A0. До открытия Colab (локально и на Drive)

1. **Собрать архив датасета** (если ещё нет на Drive):

   ```bash
   cd /path/to/BirdLense
   python3 scripts/datasets/pack_brg_for_gdrive.py
   ```

   Рядом с `binary/` и `yolo/` появится **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`**.

2. **Стартовый чекпоинт (по умолчанию — лучший с хаба):** возьмите **`best.pt`**, который **сейчас реально используется** как бинарный детектор на хабе (или локальная копия из сборки процессора, например **`app/processor/models/detection/weights/best.pt`** — если это тот же артефакт, что выкладываете в прод).

   Переименуйте при загрузке на Drive в **`bl_best.pt`** (`BASE_WEIGHTS` / «базовые боевые веса»), чтобы не перезаписать **`best.pt`** из нового обучения.

   Проверьте по возможности перед Colab:

   | Ожидание | Зачем |
   |-----------|--------|
   | задача **detect**, архитектура **YOLO11n** совместима с экспортом в прод | иначе `load`/`export` могут упасть |
   | ровно **3** класса, порядок **Bird → Rodent → Background** как в `dataset.yaml` | совпадает с [частью C](#часть-c--контракт-и-проверка) и конфигом хаба |

3. **Загрузите на Google Drive** в одну папку (рекомендуемый путь):

   `Мой диск → BirdLense_Detector`

   Там должны быть минимум:

   - `BirdLense_detector_brg_<ваш_UTC>.zip`
   - `bl_best.pt` (**обязательно в режиме по умолчанию**)

4. Убедитесь, что хватает места под раны Ultralytics на Drive (**несколько GB** и больше): **`project=RUNS`** ниже пишет в **`.../BirdLense_Detector/yolo_detector_runs/`**.

---

## A1. Где и как запускать Colab

1. Откройте **[Google Colab](https://colab.research.google.com/)**.
2. **Файл → Новый блокнот** (или загрузите свой `.ipynb`).
3. Включите GPU: **Среда выполнения → Сменить среду выполнения → T4 GPU** (или лучше) → **Сохранить**.
4. Дальше в блокноте идут **отдельные ячейки**. Для каждой: выделите ячейку → **Shift+Enter** или кнопка **▶ Выполнить** слева от ячейки. **Ячейки выполняйте по порядку сверху вниз** (иначе не будет переменных `os`, `DRIVE_ROOT`, `DATA_YAML`).

После ячейки с **`drive.mount`** браузер попросит разрешить доступ к Drive — пройдите авторизацию.

### A1.b — Обрыв сессии и `resume`

Если Colab отключился **после** старта этапа 1 или 2, не начинайте заново ту же команду **`model.train(...)`** с тем же `name`: либо укажите **`resume=True`** с **`last.pt`**, либо смените **`name`** у нового рана.

Пример после монтирования Drive (подставьте свой путь к **`last.pt`** из папки рана):

```python
from ultralytics import YOLO

LAST = "/content/drive/MyDrive/BirdLense_Detector/yolo_detector_runs/brg_ft_stage1_freeze10/weights/last.pt"
YOLO(LAST).train(resume=True)  # без прочих аргументов — так требует Ultralytics
```

Для второго этапа — аналогично, если обрыв был на **`brg_ft_stage2_full`**.

---

## A1.c — Если нет боевого `best.pt` (редкий холодный старт части A)

Имеет смысл только когда **нет** сохранённого трёхклассового чекпоинта Hub. Тогда можно стартовать с **`YOLO("yolo11n.pt")`**: Ultralytics создаст голову под **3 класса** по вашему `dataset.yaml`, но качество первых эпох будет хуже, чем при дообучении от уже натренированного BRG-детектора. После этого всё равно соблюдайте **`imgsz=640`**, два этапа и контракт классов из части **C**. Для воспроизводимости версий: **`!pip install -q ultralytics>=8.3.203`** (см. [TRAINING.ru.md](./TRAINING.ru.md) про `resume` / GradScaler).

---

## A2. Ячейки блокнота (скопировать по порядку)

### Ячейка 1 — зависимости

**Запуск:** один раз в начале сессии.

```python
# Для стабильного resume в новых сессиях Colab — не ниже 8.3.203 (см. TRAINING.ru.md)
!pip install -q "ultralytics>=8.3.203" pyyaml
```

### Ячейка 2 — подключить Google Drive

**Запуск:** один раз; подтвердите доступ в браузере.

```python
from google.colab import drive
drive.mount("/content/drive")
```

### Ячейка 3 — пути и проверка файлов

**Важно:** строка **`BirdLense_detector_brg_20260430_134305Z.zip`** в старых версиях инструкции была **только примером** — такого файла у вас на Drive нет, пока вы сами не положите ZIP.

- Либо укажите **точное имя** своего архива (как вы назвали файл при загрузке на Drive).
- Либо оставьте **авто-поиск** ниже: берётся **самый свежий по дате изменения** файл **`BirdLense_detector_brg_*.zip`** в **`DRIVE_ROOT`**.

**`BASE_WEIGHTS`** — **боевой `best.pt` с хаба** на Drive как **`bl_best.pt`**.

```python
import os
from pathlib import Path

DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Detector"
assert os.path.isdir(DRIVE_ROOT), f"Нет папки (проверьте путь и что Drive смонтирован): {DRIVE_ROOT}"

# --- Вариант A (рекомендуется): последний по времени BRG-zip в папке ---
cands = list(Path(DRIVE_ROOT).glob("BirdLense_detector_brg_*.zip"))
if not cands:
    raise FileNotFoundError(
        f"В {DRIVE_ROOT} нет BirdLense_detector_brg_*.zip. "
        "Загрузите архив с локальной машины (pack_brg_for_gdrive.py) или задайте ZIP вручную (вариант B)."
    )
ZIP_PATH = str(max(cands, key=lambda p: p.stat().st_mtime))
print("ZIP (авто):", ZIP_PATH)

# --- Вариант B: вручную раскомментируйте и подставьте имя с Drive ---
# ZIP_PATH = os.path.join(DRIVE_ROOT, "BirdLense_detector_brg_20260505_120000Z.zip")

BASE_WEIGHTS = os.path.join(DRIVE_ROOT, "bl_best.pt")
WEIGHTS = BASE_WEIGHTS

assert os.path.isfile(ZIP_PATH), f"Нет архива: {ZIP_PATH}"
assert os.path.isfile(BASE_WEIGHTS), f"Нет базовых весов: {BASE_WEIGHTS}"
print("OK:", ZIP_PATH, BASE_WEIGHTS)
```

Если не видите папку **`BirdLense_Detector`**: проверьте **реальный путь** в Drive (иногда **`Shared drives/...`** или другое имя) — поправьте **`DRIVE_ROOT`**.

### Ячейка 4 — распаковать датасет

```python
import shutil

EXTRACT = "/content/brg_dataset"
if os.path.exists(EXTRACT):
    shutil.rmtree(EXTRACT)
os.makedirs(EXTRACT, exist_ok=True)

!unzip -q "{ZIP_PATH}" -d "{EXTRACT}"
```

Ожидается файл **`/content/brg_dataset/brg/dataset.yaml`**. Если структура другая — в следующей ячейке задайте **`DATA_YAML`** вручную.

### Ячейка 5 — поправить `path` в `dataset.yaml` под Colab

```python
import yaml

DATA_YAML = "/content/brg_dataset/brg/dataset.yaml"
assert os.path.isfile(DATA_YAML), DATA_YAML

with open(DATA_YAML, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

cfg["path"] = "/content/brg_dataset/brg"

with open(DATA_YAML, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

print(cfg)

# Согласованность с боевым детектором (порядок id 0,1,2):
names = cfg.get("names") or {}
keys = sorted(names, key=lambda k: int(k))
ordered = [names[k] for k in keys]
assert ordered == ["Bird", "Rodent", "Background"], ordered
```

Если assert падает — не запускайте обучение: поправьте **`dataset.yaml`** в архиве и пересоберите ZIP.

### Ячейка 6 — этап 1: заморозка backbone (`freeze=10`)

**Запуск:** долго (десятки минут и больше). Стартуем **`YOLO(WEIGHTS)`** от **`BASE_WEIGHTS`** (= боевой чекпоинт).

При обрыве Colab — см. выше раздел **A1.b** (**`resume=True`** из **`last.pt`**); не запускайте повторно **`model.train`** с тем же **`name`**, если хотите именно продолжить ту же задачу.

```python
from ultralytics import YOLO

RUNS = os.path.join(DRIVE_ROOT, "yolo_detector_runs")
os.makedirs(RUNS, exist_ok=True)

model = YOLO(WEIGHTS)
model.train(
    data=DATA_YAML,
    epochs=40,
    imgsz=640,
    batch=16,
    freeze=10,
    patience=20,
    cache="disk",
    project=RUNS,
    name="brg_ft_stage1_freeze10",
)
```

При нехватке VRAM уменьшите **`batch`** (например **8**). При необходимости меняйте **`freeze`** (**5** … **10**).

### Ячейка 7 — этап 2: вся сеть, меньший `lr0`

```python
STAGE1_BEST = os.path.join(RUNS, "brg_ft_stage1_freeze10", "weights", "best.pt")
assert os.path.isfile(STAGE1_BEST), STAGE1_BEST

model2 = YOLO(STAGE1_BEST)
model2.train(
    data=DATA_YAML,
    epochs=60,
    imgsz=640,
    batch=16,
    lr0=0.001,
    patience=25,
    cache="disk",
    project=RUNS,
    name="brg_ft_stage2_full",
)
```

Параметр **`freeze` здесь не указываем** — учатся все слои.

### Ячейка 8 — итоговый `best.pt` и экспорт OpenVINO **640×640**

```python
BEST_FINAL = os.path.join(RUNS, "brg_ft_stage2_full", "weights", "best.pt")
assert os.path.isfile(BEST_FINAL), BEST_FINAL
print("YOLO best:", BEST_FINAL)

export_model = YOLO(BEST_FINAL)
export_model.export(format="openvino", imgsz=640)
```

Ultralytics 8.x печатает в конце **точный путь** к каталогу IR; обычно это **`.../weights/best_openvino_model/`** рядом с **`best.pt`** (файлы **`best.xml`**, **`best.bin`**, **`metadata.yaml`**). Если имя отличается — ориентируйтесь на вывод строки **`OpenVINO: export success`**.

В **`metadata.yaml`** после экспорта должно быть **3 класса** в том же порядке, что в датасете.

### A3. После Colab — что забрать на хаб

1. **`.../brg_ft_stage2_full/weights/best.pt`** на Drive — новый торч‑детектор для хаба / замена **`bl_best.pt`** при следующей итерации.
2. Каталог **OpenVINO** из вывода экспорта (часто **`best_openvino_model`**) целиком — в приложении типичный путь **`models/detection/weights/best_openvino_model`** относительно корня процессора; **`processor.binary_imgsz: 640`** ([CONFIGURATION.ru.md](./CONFIGURATION.ru.md)).

### Упрощение (один прогон вместо ячеек 6–7)

Одна длинная тренировка с **`BASE_WEIGHTS`** (тот же **`WEIGHTS`** / **`bl_best.pt`**):

```python
model = YOLO(WEIGHTS)
model.train(
    data=DATA_YAML,
    epochs=80,
    imgsz=640,
    batch=16,
    freeze=10,
    patience=30,
    cache="disk",
    project=RUNS,
    name="brg_ft_single_freeze10",
)
```

Затем в ячейке экспорта подставьте **`.../brg_ft_single_freeze10/weights/best.pt`**.

---

# Часть B — Дополнительно: binary balanced → full (Hugging Face)

Отдельный сценарий для архивов **`detector_merged_balanced_*.zip`** и **`detector_merged_full_*.zip`** из [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main). Здесь **`imgsz=960`** и старт **`YOLO("yolo11n.pt")`** (Ultralytics подтянет веса сам). **Не смешивайте** с частью A без понимания разницы путей и размера входа.

**Где запускать:** тот же Colab, можно вторым блокнотом или ниже по тем же правилам (GPU → ячейки по порядку).

### B1. Подготовка Drive

Загрузите оба ZIP в **`MyDrive/BirdLense_Detector/`** и запомните имена файлов.

### B2. Ячейки

**Ячейка B-a — зависимости и Drive** (как в части A: `pip`, `drive.mount`).

**Ячейка B-b — константы**

```python
import os
import shutil
import yaml

DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Detector"
ZIP_BALANCED = "detector_merged_balanced_20260429.zip"  # ваше имя
ZIP_FULL = "detector_merged_full_20260429.zip"
```

**Ячейка B-c — Stage A: распаковать balanced**

```python
EXTRACT_A = "/content/data_stage_a"
if os.path.exists(EXTRACT_A):
    shutil.rmtree(EXTRACT_A)
os.makedirs(EXTRACT_A, exist_ok=True)
!unzip -q "{DRIVE_ROOT}/{ZIP_BALANCED}" -d "{EXTRACT_A}"
```

**Ячейка B-d — Stage A: `dataset.yaml`**

```python
DATA_YAML_A = "/content/data_stage_a/binary/merged_balanced/dataset.yaml"
assert os.path.isfile(DATA_YAML_A), DATA_YAML_A
with open(DATA_YAML_A, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg["path"] = "/content/data_stage_a/binary/merged_balanced"
with open(DATA_YAML_A, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
print(cfg)
```

**Ячейка B-e — Stage A: train**

```python
from ultralytics import YOLO

model_a = YOLO("yolo11n.pt")
model_a.train(
    data=DATA_YAML_A,
    epochs=80,
    imgsz=960,
    batch=16,
    patience=20,
    project=f"{DRIVE_ROOT}/yolo_detector_runs",
    name="stage_a_balanced",
)
```

**Ячейка B-f — путь к best Stage A**

```python
BEST_A = f"{DRIVE_ROOT}/yolo_detector_runs/stage_a_balanced/weights/best.pt"
print(BEST_A)
```

**Ячейка B-g — Stage B: распаковать full**

```python
EXTRACT_B = "/content/data_stage_b"
if os.path.exists(EXTRACT_B):
    shutil.rmtree(EXTRACT_B)
os.makedirs(EXTRACT_B, exist_ok=True)
!unzip -q "{DRIVE_ROOT}/{ZIP_FULL}" -d "{EXTRACT_B}"
```

**Ячейка B-h — Stage B: `dataset.yaml`**

```python
DATA_YAML_B = "/content/data_stage_b/binary/merged/dataset.yaml"
assert os.path.isfile(DATA_YAML_B), DATA_YAML_B
with open(DATA_YAML_B, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg["path"] = "/content/data_stage_b/binary/merged"
with open(DATA_YAML_B, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
print(cfg)
```

**Ячейка B-i — Stage B: fine-tune**

```python
model_b = YOLO(BEST_A)
model_b.train(
    data=DATA_YAML_B,
    epochs=40,
    imgsz=960,
    batch=16,
    lr0=0.003,
    patience=15,
    project=f"{DRIVE_ROOT}/yolo_detector_runs",
    name="stage_b_full_ft",
)
```

**Ячейка B-j — OpenVINO (размер должен совпадать с обучением)**

```python
BEST_B = f"{DRIVE_ROOT}/yolo_detector_runs/stage_b_full_ft/weights/best.pt"
export_model = YOLO(BEST_B)
export_model.export(format="openvino", imgsz=960)
```

На хабе **`processor.binary_imgsz`** должен быть **960** для этого экспорта.

Готовый пакет **`weights-*-001.zip`** с HF можно положить на хаб без этого пайплайна — см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md).

---

# Часть C — Контракт и проверка

Имена классов для трёхклассового детектора на хабе: **Bird**, **Rodent**, **Background**; **`processor.detector_scope`** без Background — [CV_ML_PREP.ru.md](./CV_ML_PREP.ru.md).

Локально перед продом:

```bash
make validate-weights BINARY=/path/to/best.pt ...
```

Регрессия по клипам: `scripts/benchmark-track-regen.py` — [TRAINING.ru.md](./TRAINING.ru.md).
