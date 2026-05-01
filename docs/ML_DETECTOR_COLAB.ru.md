# Обучение детектора (YOLO) в Google Colab

[English](./ML_DETECTOR_COLAB.md)

Классификатор — [TRAINING.ru.md](./TRAINING.ru.md). Здесь только **детекция** (`dataset.yaml`). Пути к **`brg/`**, merge, упаковка ZIP — [DATASETS.ru.md](./DATASETS.ru.md).

---

## Оглавление

| Часть | О чём |
|--------|--------|
| **A** | Основной сценарий: **`brg` ZIP + `bl_best.pt`**, два этапа обучения (`freeze` → full), OpenVINO **640** — **от нуля до выгрузки на хаб** |
| **B** | Дополнительно: старый **binary** пайплайн с Hugging Face (balanced → full, **`yolo11n.pt`**, **960**) |
| **C** | Контракт классов, проверка перед продом |

---

# Часть A — Основной сценарий (`brg` + `bl_best.pt`)

## A0. До открытия Colab (локально и на Drive)

1. **Собрать архив датасета** (если ещё нет на Drive):

   ```bash
   cd /path/to/BirdLense
   python3 scripts/datasets/pack_brg_for_gdrive.py
   ```

   В корне появится **`datasets/BirdLense_detector_brg_<UTC>.zip`** (каталог `datasets/` в `.gitignore`).

2. **Взять чекпоинт для дообучения:** скопируйте с машины, где лежат веса хаба, файл вида **`best.pt`** (активный детектор **YOLO11n**) и назовите на Drive **`bl_best.pt`** — так проще не перепутать с результатами нового рана.

3. **Загрузите на Google Drive** в одну папку (рекомендуемый путь):

   `Мой диск → BirdLense_Detector`

   Там должны быть минимум:

   - `BirdLense_detector_brg_<ваш_UTC>.zip`
   - `bl_best.pt`

4. Убедитесь, что хватает места под раны Ultralytics на Drive (~несколько GB): ниже **`project=RUNS`** пишет в **`.../BirdLense_Detector/yolo_detector_runs/`**.

---

## A1. Где и как запускать Colab

1. Откройте **[Google Colab](https://colab.research.google.com/)**.
2. **Файл → Новый блокнот** (или загрузите свой `.ipynb`).
3. Включите GPU: **Среда выполнения → Сменить среду выполнения → T4 GPU** (или лучше) → **Сохранить**.
4. Дальше в блокноте идут **отдельные ячейки**. Для каждой: выделите ячейку → **Shift+Enter** или кнопка **▶ Выполнить** слева от ячейки. **Ячейки выполняйте по порядку сверху вниз** (иначе не будет переменных `os`, `DRIVE_ROOT`, `DATA_YAML`).

После ячейки с **`drive.mount`** браузер попросит разрешить доступ к Drive — пройдите авторизацию.

---

## A2. Ячейки блокнота (скопировать по порядку)

### Ячейка 1 — зависимости

**Запуск:** один раз в начале сессии.

```python
!pip install -q ultralytics pyyaml
```

### Ячейка 2 — подключить Google Drive

**Запуск:** один раз; подтвердите доступ в браузере.

```python
from google.colab import drive
drive.mount("/content/drive")
```

### Ячейка 3 — пути и проверка файлов

**Запуск:** поправьте **`ZIP_NAME`** под имя вашего архива на Drive.

```python
import os

DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Detector"
ZIP_NAME = "BirdLense_detector_brg_20260430_134305Z.zip"  # <-- ваш файл
ZIP_PATH = os.path.join(DRIVE_ROOT, ZIP_NAME)
WEIGHTS = os.path.join(DRIVE_ROOT, "bl_best.pt")

assert os.path.isfile(ZIP_PATH), f"Нет архива: {ZIP_PATH}"
assert os.path.isfile(WEIGHTS), f"Нет весов: {WEIGHTS}"
print("OK:", ZIP_PATH, WEIGHTS)
```

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
```

В выводе проверьте **`names`**: Bird, Rodent, Background.

### Ячейка 6 — этап 1: заморозка backbone (`freeze=10`)

**Запуск:** долго (десятки минут и больше). Не закрывайте вкладку; при обрыве сессии можно снова смонтировать Drive и продолжить со следующей ячейки, если папка рана уже создана.

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

Экспорт появится **рядом** с каталогом весов (типично подпапка с суффиксом **`_openvino`** в том же run — смотрите вывод Ultralytics). Нужны **`.xml`**, **`.bin`**, **`metadata.yaml`**.

### A3. После Colab — что забрать на хаб

1. На **Google Drive** в **`BirdLense_Detector/yolo_detector_runs/brg_ft_stage2_full/weights/best.pt`** — скачайте как новый детектор.
2. Папку **OpenVINO** из того же рана — в конфиге хаба выставьте **`processor.binary_imgsz: 640`** и пути к бинарнику ([CONFIGURATION.ru.md](./CONFIGURATION.ru.md)).

### Упрощение (один прогон вместо ячеек 6–7)

Одна длинная тренировка от **`bl_best.pt`**:

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
