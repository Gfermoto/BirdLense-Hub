# Обучение BRG-детектора в Google Colab

Три класса: **Bird / Rodent / Background**, **`imgsz=640`**, экспорт OpenVINO под хаб.  
Ссылки: классификатор — [TRAINING.ru.md](./TRAINING.ru.md), датасет — [DATASETS.ru.md](./DATASETS.ru.md), прочее — [ML_DETECTOR_COLAB.md](./ML_DETECTOR_COLAB.md).

---

## Как читать документ

| Ситуация | Раздел |
|----------|--------|
| Первый раз учишь с нуля | **Сценарий 1** (ниже) |
| Обрыв **во время** ячейки 6 или 7 | **Сценарий 2** (таблица → вариант **А**, **Б** или **В**) |
| Этап 1 уже добит, этап 2 не запускал | **Сценарий 2, вариант Б** |
| Есть финальный `best.pt`, нужен только IR | **Ячейка 8** (сценарий 1) |

**На Google Диске** папка **`Мой диск/3step_detector/`**:

- **`BirdLense_detector_brg.zip`** — при необходимости переименовать (если в имени была дата сборки).
- **`nabirds_yolo11n_binary.zip`** — стартовый **`.pt`** (часто один класс `bird`; голову под три класса пересоберёт `train` по `dataset.yaml`).

В Colab: среда **GPU (T4 и лучше)**.

---

## Сценарий 1 — первый запуск

Выполняй **ячейки 1 → 8** подряд.

### Ячейка 1 — зависимости

```python
!pip install -q "ultralytics>=8.3.203" pyyaml
```

### Ячейка 2 — Диск

```python
from google.colab import drive
drive.mount("/content/drive")
```

### Ячейка 3 — веса + датасет на `/content`

Путь к папке на Диске при Shared Drive поменяй в **`DRIVE_ROOT`**.

```python
import os
import shutil
from pathlib import Path

DRIVE_ROOT = "/content/drive/MyDrive/3step_detector"
ZIP_DATA = os.path.join(DRIVE_ROOT, "BirdLense_detector_brg.zip")
ZIP_WEIGHTS = os.path.join(DRIVE_ROOT, "nabirds_yolo11n_binary.zip")

assert os.path.isfile(ZIP_DATA), ZIP_DATA
assert os.path.isfile(ZIP_WEIGHTS), ZIP_WEIGHTS

WT_EXTRACT = "/content/nabirds_binary_weights_unzip"
if os.path.exists(WT_EXTRACT):
    shutil.rmtree(WT_EXTRACT)
os.makedirs(WT_EXTRACT, exist_ok=True)
!unzip -q "{ZIP_WEIGHTS}" -d "{WT_EXTRACT}"

root = Path(WT_EXTRACT)
best_cands = list(root.rglob("best.pt"))
all_pt = list(root.rglob("*.pt"))
if best_cands:
    WEIGHTS = str(sorted(best_cands, key=lambda p: len(str(p)))[0])
elif len(all_pt) == 1:
    WEIGHTS = str(all_pt[0])
else:
    raise FileNotFoundError("Нет однозначного .pt: " + ", ".join(str(p) for p in all_pt[:30]))

EXTRACT = "/content/brg_dataset"
if os.path.exists(EXTRACT):
    shutil.rmtree(EXTRACT)
os.makedirs(EXTRACT, exist_ok=True)
!unzip -q "{ZIP_DATA}" -d "{EXTRACT}"

RUNS = os.path.join(DRIVE_ROOT, "yolo_detector_runs")
os.makedirs(RUNS, exist_ok=True)

print("WEIGHTS:", WEIGHTS)
print("RUNS:", RUNS)
```

### Ячейка 4 — `dataset.yaml` + проверка split-ов

```python
import yaml
from pathlib import Path

EXTRACT = "/content/brg_dataset"

yaml_cands = sorted(Path(EXTRACT).rglob("dataset.yaml"))
assert yaml_cands, f"dataset.yaml не найден под {EXTRACT}"

picked = None
for c in yaml_cands:
    base = c.parent
    if all((base / split / "images").is_dir() for split in ("train", "val", "test")):
        picked = c
        break
if picked is None:
    picked = yaml_cands[0]

DATA_YAML = str(picked)
DATA_ROOT = str(picked.parent)
print("DATA_YAML:", DATA_YAML)
print("DATA_ROOT:", DATA_ROOT)

with open(DATA_YAML, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg["path"] = DATA_ROOT
with open(DATA_YAML, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

for split in ("train", "val", "test"):
    img_dir = Path(DATA_ROOT) / split / "images"
    lbl_dir = Path(DATA_ROOT) / split / "labels"
    assert img_dir.is_dir(), f"Нет каталога: {img_dir}"
    assert lbl_dir.is_dir(), f"Нет каталога: {lbl_dir}"
    print(f"{split}: images={img_dir} labels={lbl_dir}")

names = cfg.get("names") or {}
ordered = [names[k] for k in sorted(names, key=lambda k: int(k))]
assert ordered == ["Bird", "Rodent", "Background"], ordered
```

### Ячейка 5 — чекпоинт только `detect`

Имена классов в **`WEIGHTS`** могут не совпадать с BRG (например один `bird`) — это нормально.

```python
import yaml
from ultralytics import YOLO

m = YOLO(WEIGHTS)
assert str(getattr(m, "task", None) or "").lower() == "detect", m.task

nm = m.names if m.names is not None else {}
ckpt_labels = [nm[k] for k in sorted(nm.keys(), key=lambda x: int(x))] if isinstance(nm, dict) else list(nm)

with open(DATA_YAML, "r", encoding="utf-8") as f:
    data_names = yaml.safe_load(f).get("names") or {}
wanted = [data_names[k] for k in sorted(data_names, key=lambda k: int(k))]

print("Чекпоинт:", ckpt_labels, "| датасет:", wanted)
if ckpt_labels != wanted:
    print("(ok) train пересоберёт голову под датасет.")
```

### Ячейка 6 — этап 1 (freeze)

Долго. Не хватает VRAM — уменьши **`batch`**.

```python
from ultralytics import YOLO

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

### Ячейка 7 — этап 2 (full)

```python
from ultralytics import YOLO
import os

STAGE1_BEST = os.path.join(RUNS, "brg_ft_stage1_freeze10", "weights", "best.pt")
assert os.path.isfile(STAGE1_BEST), STAGE1_BEST

YOLO(STAGE1_BEST).train(
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

### Ячейка 8 — OpenVINO 640

```python
from ultralytics import YOLO
import os

BEST_FINAL = os.path.join(RUNS, "brg_ft_stage2_full", "weights", "best.pt")
assert os.path.isfile(BEST_FINAL), BEST_FINAL
YOLO(BEST_FINAL).export(format="openvino", imgsz=640)
```

Путь к каталогу IR — в конце лога экспорта.

---

## Сценарий 2 — Colab закрылся или сессия оборвалась во время обучения

### Зачем отдельный сценарий

- Папка **`/content`** в Colab после перезапуска **пустая** — распакованный датасет нужно **положить заново** (ниже «Общие шаги»).
- Прогресс обучения (**`last.pt`**, **`best.pt`**) Ultralytics пишет на **Google Диск** в **`3step_detector/yolo_detector_runs/`** — он **не пропадает**.
- **Продолжить тот же тренировочный прогон** можно только так:  
  `YOLO("<путь>/last.pt").train(resume=True)` — **без** `data=`, `epochs=` и других аргументов.

### Выбери один вариант

Ответь, на чём ты остановился:

| Ситуация | Вариант |
|---------|---------|
| Обучение **ещё не начинал** (не дошёл до ячейки 6) | Не этот раздел. Открой **Сценарий 1**: с ячейки **3**, если `/content` пустой — с ячейки **1**. |
| Ячейка **6** была **запущена**, но Colab выгнал **до конца** всех эпох либо ты прервал посередине | **А — resume этапа 1** |
| Ячейка **6 уже полностью отработала** в прошлый раз (видел финиш train), но ячейку **7 не запускал** или ноутбук закрыли | **Б — только этап 2** |
| Ячейка **7** была **запущена**, но сессия оборвалась **до конца** эпох | **В — resume этапа 2** |

### Общие шаги О1–О3 (сначала всегда их, если выбрал А, Б или В)

**О1** — то же, что **ячейка 1** в сценарии 1 (`pip`).

**О2** — то же, что **ячейка 2** в сценарии 1 (`drive.mount`).

**О3** — одна ячейка: снова распаковать **`BirdLense_detector_brg.zip`**, авто-найти `dataset.yaml`, поправить `path` и проверить split-ы (`train/val/test`). Стартовые веса из **`nabirds…zip`** не нужны (для А и В берётся **`last.pt`** с Диска; для Б — **`best.pt`** этапа 1 с Диска).

**Важно:** Python-блок сразу ниже — это **только О3**. **О1** и **О2** — это **две предыдущие** отдельные ячейки (как в сценарии 1); их сюда не вставляй.

```python
import os
import shutil
import yaml
from pathlib import Path

DRIVE_ROOT = "/content/drive/MyDrive/3step_detector"
ZIP_DATA = os.path.join(DRIVE_ROOT, "BirdLense_detector_brg.zip")
RUNS = os.path.join(DRIVE_ROOT, "yolo_detector_runs")

assert os.path.isfile(ZIP_DATA), ZIP_DATA

EXTRACT = "/content/brg_dataset"
if os.path.exists(EXTRACT):
    shutil.rmtree(EXTRACT)
os.makedirs(EXTRACT, exist_ok=True)
!unzip -q "{ZIP_DATA}" -d "{EXTRACT}"

yaml_cands = sorted(Path(EXTRACT).rglob("dataset.yaml"))
assert yaml_cands, f"dataset.yaml не найден под {EXTRACT}"

picked = None
for c in yaml_cands:
    base = c.parent
    if all((base / split / "images").is_dir() for split in ("train", "val", "test")):
        picked = c
        break
if picked is None:
    picked = yaml_cands[0]

DATA_YAML = str(picked)
DATA_ROOT = str(picked.parent)

with open(DATA_YAML, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg["path"] = DATA_ROOT
with open(DATA_YAML, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

for split in ("train", "val", "test"):
    img_dir = Path(DATA_ROOT) / split / "images"
    lbl_dir = Path(DATA_ROOT) / split / "labels"
    assert img_dir.is_dir(), f"Нет каталога: {img_dir}"
    assert lbl_dir.is_dir(), f"Нет каталога: {lbl_dir}"
    print(f"{split}: images={img_dir} labels={lbl_dir}")

names = cfg.get("names") or {}
assert [names[k] for k in sorted(names, key=lambda k: int(k))] == ["Bird", "Rodent", "Background"]
print("DATA_YAML:", DATA_YAML)
print("DATA_ROOT:", DATA_ROOT)
print("RUNS (папка чекпоинтов на Диске):", RUNS)
```

### Вариант А — продолжить **недоконченный** этап 1

После **О1 → О2 → О3** выполни **только** эту ячейку:

```python
import os
from ultralytics import YOLO

DRIVE_ROOT = "/content/drive/MyDrive/3step_detector"
LAST = os.path.join(DRIVE_ROOT, "yolo_detector_runs", "brg_ft_stage1_freeze10", "weights", "last.pt")

assert os.path.isfile(LAST), LAST
YOLO(LAST).train(resume=True)
```

Когда этап 1 **дойдёт до конца**, запускай **Вариант Б** (перед этапом 2 снова **О1–О3**, если откроешь новую сессию).

### Вариант Б — этап 1 уже закончен, нужен **чистый старт этапа 2**

На Диске должен существовать файл  
`…/brg_ft_stage1_freeze10/weights/best.pt`.  
**`resume` не используем** — это новый run с именем `brg_ft_stage2_full`.

После **О1 → О2 → О3** выполни:

```python
from ultralytics import YOLO
import os

DRIVE_ROOT = "/content/drive/MyDrive/3step_detector"
RUNS = os.path.join(DRIVE_ROOT, "yolo_detector_runs")
DATA_YAML = "/content/brg_dataset/brg/dataset.yaml"

STAGE1_BEST = os.path.join(RUNS, "brg_ft_stage1_freeze10", "weights", "best.pt")
assert os.path.isfile(STAGE1_BEST), STAGE1_BEST

YOLO(STAGE1_BEST).train(
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

Дальше — **ячейка 8** из сценария 1 (OpenVINO), когда этап 2 закончится.

### Вариант В — продолжить **недоконченный** этап 2

После **О1 → О2 → О3** выполни **только** эту ячейку:

```python
import os
from ultralytics import YOLO

DRIVE_ROOT = "/content/drive/MyDrive/3step_detector"
LAST = os.path.join(DRIVE_ROOT, "yolo_detector_runs", "brg_ft_stage2_full", "weights", "last.pt")

assert os.path.isfile(LAST), LAST
YOLO(LAST).train(resume=True)
```

После успешного окончания — **ячейка 8** из сценария 1.

### Чего не делать

- Не запускай повторно **ячейку 6** целиком, если хочешь **продолжить** тот же этап 1 — только **Вариант А**.
- Не запускай **ячейку 7** второй раз «с нуля», если этап 2 уже **частично** шёл — только **Вариант В** с `last.pt` этапа 2.

---

## После Colab

1. На Диске: `yolo_detector_runs/brg_ft_stage2_full/weights/best.pt` и каталог OpenVINO из экспорта.
2. Локально:

```bash
make validate-weights BINARY=/path/to/best.pt
```

Контракт: [CV_ML_PREP.ru.md](./CV_ML_PREP.ru.md), пути: [CONFIGURATION.ru.md](./CONFIGURATION.ru.md).

---

## Если в zip весов нет подходящего `.pt`

Старт: `YOLO("yolo11n.pt")` вместо `YOLO(WEIGHTS)` в **ячейке 6**, те же `data` / `imgsz` / этапы — хуже, чем со своим чекпоинтом.
